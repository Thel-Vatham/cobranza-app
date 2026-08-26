from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db, limiter
from ..models import User
from ..services.financial import log_audit

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.active:
                flash("El usuario está inactivo. Contacte al administrador.", "danger")
                return render_template("login.html")
            login_user(user)
            log_audit(user.id, "Inicio de sesión", "Usuario", user.id)
            db.session.commit()
            return redirect(request.args.get("next") or url_for("dashboard.index"))
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    log_audit(current_user.id, "Cierre de sesión", "Usuario", current_user.id)
    db.session.commit()
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))
