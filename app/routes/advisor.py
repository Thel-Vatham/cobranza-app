from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Audit, Client, ClientReferral, Notification, User
from ..services.financial import log_audit
from ..services.scoring import compute_score

bp = Blueprint("advisor", __name__, url_prefix="/asesor")


def _is_authorized_advisor():
    if not current_user.is_authenticated:
        return False
    role_name = current_user.role.name if current_user.role else ""
    return role_name in ("Consulta", "Administrador")


@bp.route("/")
@login_required
def index():
    if not _is_authorized_advisor():
        flash("Acceso restringido a asesores y consultores de crédito.", "danger")
        return redirect(url_for("dashboard.index"))

    is_admin = current_user.role and current_user.role.name == "Administrador"

    # Notificaciones del usuario actual
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(15).all()

    # Remisiones de clientes
    if is_admin:
        referrals = ClientReferral.query.order_by(ClientReferral.created_at.desc()).all()
    else:
        referrals = ClientReferral.query.filter_by(advisor_id=current_user.id).order_by(ClientReferral.created_at.desc()).all()

    # Calcular indicadores del panel de asesoría
    total_referred = len(referrals)
    in_overdue_count = 0
    total_debt = 0.0
    total_overdue = 0.0

    client_items = []
    for ref in referrals:
        client = ref.client
        score_data = compute_score(client)
        is_overdue = client.is_in_overdue
        debt = client.total_outstanding
        overdue_val = client.total_overdue

        if is_overdue:
            in_overdue_count += 1
        total_debt += debt
        total_overdue += overdue_val

        client_items.append({
            "referral": ref,
            "client": client,
            "score": score_data,
            "is_overdue": is_overdue,
            "total_debt": debt,
            "total_overdue": overdue_val,
        })

    indicators = {
        "total_referred": total_referred,
        "in_overdue_count": in_overdue_count,
        "total_debt": total_debt,
        "total_overdue": total_overdue,
    }

    return render_template(
        "advisor/dashboard.html",
        indicators=indicators,
        notifications=notifications,
        client_items=client_items,
        is_admin=is_admin,
    )


@bp.route("/cliente/<int:client_id>")
@login_required
def client_detail(client_id):
    if not _is_authorized_advisor():
        flash("Acceso restringido.", "danger")
        return redirect(url_for("dashboard.index"))

    client = Client.query.get_or_404(client_id)
    score_data = compute_score(client)

    # Remisión más reciente para este asesor
    is_admin = current_user.role and current_user.role.name == "Administrador"
    if is_admin:
        referral = ClientReferral.query.filter_by(client_id=client.id).order_by(ClientReferral.created_at.desc()).first()
    else:
        referral = ClientReferral.query.filter_by(client_id=client.id, advisor_id=current_user.id).order_by(ClientReferral.created_at.desc()).first()

    return render_template(
        "advisor/client_detail.html",
        client=client,
        score=score_data,
        referral=referral,
        is_admin=is_admin,
    )


@bp.route("/cliente/<int:client_id>/dictamen", methods=["POST"])
@login_required
def save_dictamen(client_id):
    if not _is_authorized_advisor():
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("dashboard.index"))

    client = Client.query.get_or_404(client_id)
    referral_id = request.form.get("referral_id", type=int)
    referral = ClientReferral.query.get(referral_id) if referral_id else None

    if referral:
        referral.advisor_notes = request.form.get("advisor_notes", "").strip()
        referral.status = request.form.get("status", "revisado")
        db.session.commit()
        log_audit(current_user.id, "Dictamen de asesoría", "Cliente", client.id, f"Cliente {client.full_name}")
        db.session.commit()
        flash("Dictamen de asesoría registrado correctamente.", "success")
    else:
        flash("No se encontró la remisión correspondiente.", "warning")

    return redirect(url_for("advisor.client_detail", client_id=client.id))


@bp.route("/notificaciones")
@login_required
def notifications():
    if not _is_authorized_advisor():
        flash("Acceso restringido.", "danger")
        return redirect(url_for("dashboard.index"))

    all_notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("advisor/notifications.html", notifications=all_notifs)


@bp.route("/notificaciones/<int:notif_id>/leer", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    target_link = notif.link or url_for("advisor.index")
    return redirect(target_link)


@bp.route("/notificaciones/leer-todas", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Todas las notificaciones han sido marcadas como leídas.", "info")
    return redirect(request.referrer or url_for("advisor.notifications"))
