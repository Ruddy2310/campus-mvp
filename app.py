import hmac
import secrets

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

import db
from auth_utils import HOME_ENDPOINT, load_current_user
from config import Config


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.teardown_appcontext(db.close_db)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from routes.admin import bp as admin_bp
    from routes.auth import bp as auth_bp
    from routes.faculty import bp as faculty_bp
    from routes.student import bp as student_bp

    for blueprint in (auth_bp, faculty_bp, student_bp, admin_bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def before_request():
        if request.endpoint == "static":
            return
        load_current_user()
        if request.method == "POST":
            sent = request.form.get("_csrf", "")
            expected = session.get("_csrf", "")
            if not expected or not hmac.compare_digest(sent, expected):
                abort(400, "Your session expired. Reload the page and try again.")

    @app.route("/")
    def index():
        if g.user is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for(HOME_ENDPOINT[g.user["role"]]))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def http_error(error):
        return render_template("error.html", error=error), error.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
