from decimal import Decimal
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Audit, Client, Loan, Portfolio, Role, User
from ..services.financial import log_audit

bp = Blueprint("portfolios", __name__, url_prefix="/carteras")


def _generate_code():
    count = Portfolio.query.count() + 1
    return f"CART-{count:04d}"


def _is_admin():
    return current_user.is_authenticated and current_user.role and current_user.role.name == "Administrador"


def _get_collection_operators():
    """Obtiene exclusivamente los usuarios activos con rol de Operador de cobranza."""
    return (
        User.query.join(Role)
        .filter(
            Role.name.in_(["Operador de cobranza", "Operador"]),
            User.active == True,
        )
        .order_by(User.full_name, User.username)
        .all()
    )


@bp.route("/")
@login_required
def list_portfolios():
    if _is_admin():
        portfolios = Portfolio.query.order_by(Portfolio.created_at.desc()).all()
    else:
        portfolios = Portfolio.query.filter_by(user_id=current_user.id).order_by(Portfolio.created_at.desc()).all()

    active_id = session.get("active_portfolio_id")
    return render_template(
        "portfolios/list.html",
        portfolios=portfolios,
        active_id=active_id,
        is_admin=_is_admin(),
    )


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
def create():
    if not _is_admin():
        flash("Solo los administradores pueden crear nuevas carteras.", "danger")
        return redirect(url_for("portfolios.list_portfolios"))

    operators = _get_collection_operators()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip() or _generate_code()
        description = request.form.get("description", "").strip()
        assigned_capital = request.form.get("assigned_capital_usd", "0").replace("$", "").replace(",", "").strip()
        user_id = request.form.get("user_id", type=int)

        if not name:
            flash("El nombre de la cartera es obligatorio.", "danger")
            return render_template("portfolios/form.html", portfolio=None, operators=operators, default_code=_generate_code())

        if Portfolio.query.filter_by(code=code).first():
            flash(f"El código {code} ya está en uso.", "danger")
            return render_template("portfolios/form.html", portfolio=None, operators=operators, default_code=_generate_code())

        try:
            assigned_decimal = Decimal(assigned_capital)
        except Exception:
            assigned_decimal = Decimal("0.00")

        portfolio = Portfolio(
            name=name,
            code=code,
            description=description,
            assigned_capital_usd=assigned_decimal,
            user_id=user_id,
            status=request.form.get("status", "activa"),
        )
        db.session.add(portfolio)
        db.session.commit()

        log_audit(current_user.id, "Crear cartera", "Cartera", portfolio.id, f"{portfolio.name} ({portfolio.code})")
        db.session.commit()

        flash(f"Cartera '{portfolio.name}' creada exitosamente con ${assigned_decimal:,.2f} USD.", "success")
        return redirect(url_for("portfolios.detail", portfolio_id=portfolio.id))

    return render_template(
        "portfolios/form.html",
        portfolio=None,
        operators=operators,
        default_code=_generate_code(),
    )


@bp.route("/<int:portfolio_id>")
@login_required
def detail(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    # Validar acceso
    if not _is_admin() and portfolio.user_id != current_user.id:
        flash("No tiene permisos para acceder a esta cartera.", "danger")
        return redirect(url_for("portfolios.list_portfolios"))

    clients = portfolio.clients
    loans = portfolio.loans

    return render_template(
        "portfolios/detail.html",
        portfolio=portfolio,
        clients=clients,
        loans=loans,
        is_admin=_is_admin(),
    )


@bp.route("/<int:portfolio_id>/editar", methods=["GET", "POST"])
@login_required
def edit(portfolio_id):
    if not _is_admin():
        flash("Solo los administradores pueden editar carteras.", "danger")
        return redirect(url_for("portfolios.detail", portfolio_id=portfolio_id))

    portfolio = Portfolio.query.get_or_404(portfolio_id)
    operators = _get_collection_operators()
    if portfolio.user and portfolio.user not in operators:
        operators = [portfolio.user] + operators

    if request.method == "POST":
        portfolio.name = request.form.get("name", "").strip() or portfolio.name
        portfolio.description = request.form.get("description", "").strip()
        portfolio.user_id = request.form.get("user_id", type=int)
        portfolio.status = request.form.get("status", "activa")

        assigned_capital = request.form.get("assigned_capital_usd", "0").replace("$", "").replace(",", "").strip()
        try:
            portfolio.assigned_capital_usd = Decimal(assigned_capital)
        except Exception:
            pass

        log_audit(current_user.id, "Editar cartera", "Cartera", portfolio.id, f"{portfolio.name}")
        db.session.commit()

        flash(f"Cartera '{portfolio.name}' actualizada correctamente.", "success")
        return redirect(url_for("portfolios.detail", portfolio_id=portfolio.id))

    return render_template(
        "portfolios/form.html",
        portfolio=portfolio,
        operators=operators,
        default_code=portfolio.code,
    )


@bp.route("/alternar/<int:portfolio_id>", methods=["GET", "POST"])
@login_required
def switch(portfolio_id):
    """Permite cambiar la cartera activa en la sesión o volver a vista global (id=0)."""
    if portfolio_id == 0:
        if not _is_admin():
            flash("Solo el administrador puede visualizar la vista global de todas las carteras.", "warning")
            return redirect(url_for("portfolios.list_portfolios"))
        session["active_portfolio_id"] = None
        flash("Vista Global activada: visualizando todas las carteras.", "info")
    else:
        portfolio = Portfolio.query.get_or_404(portfolio_id)
        if not _is_admin() and portfolio.user_id != current_user.id:
            flash("No tiene permisos para activar esta cartera.", "danger")
            return redirect(url_for("portfolios.list_portfolios"))

        session["active_portfolio_id"] = portfolio.id
        flash(f"Cartera activa: {portfolio.name} ({portfolio.code})", "success")

    next_url = request.args.get("next") or request.referrer or url_for("dashboard.index")
    return redirect(next_url)
