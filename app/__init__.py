from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'login'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.routes.admin_routes import admin_bp
    from app.routes.user_routes import user_bp
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):  
        return User.query.get(int(user_id))      
        
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)

    with app.app_context():
        db.create_all() 

        if not User.query.filter_by(username='admin').first():
                admin = User(
                username='admin',
                email='admin@gmail.com',
                password=generate_password_hash('admin'),
                role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("Admin user created.")
    return app