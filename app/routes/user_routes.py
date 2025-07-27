from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user, login_user, logout_user
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import ParkingLot, ParkingSpot, Reservation, User
from datetime import datetime 
from datetime import timedelta 
from collections import defaultdict
from sqlalchemy.orm import joinedload

user_bp= Blueprint('user', __name__)

@user_bp.route('/')
def index():
    return render_template('index.html')

@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')
        pin_code = request.form.get('pincode')
        phone_number = request.form.get('phone_number')
        vehicle_number = request.form.get('vehicle_number')
        
        if role == 'admin':
            flash('Admin registration not allowed')
            return redirect(url_for('user.register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('user.register'))

        hashed_pw = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw,
            role=role,
            pin_code=pin_code,
            phone_number=phone_number,
            vehicle_number=vehicle_number
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('user.login'))
    return render_template('register.html')

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            # flash('Login successful.')

            if user.role == 'user': 
                return redirect(url_for('user.user_dashboard'))
            else:
                return redirect(url_for('admin.admin_dashboard'))
    
        else:
            flash('Invalid credentials. Please try again.')
            return redirect(url_for('user.login'))
    return render_template('login.html')

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('user.index'))

@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    lots = ParkingLot.query.all()

    active_reservations = (
        db.session.query(Reservation)
        .join(ParkingSpot)
        .filter(
            Reservation.user_id == current_user.id,
            Reservation.leaving_time == None
        ).all()
    )

    reservation_map = {}
    for res in active_reservations:
        reservation_map[res.spot.lot_id] = res

    return render_template('user_templates/dashboard_user.html', lots=lots, active_reservations=active_reservations, timedelta=timedelta, reservation_map=reservation_map)

@user_bp.route('/history')
@login_required
def reservation_history():
    reservations = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.parking_time.desc()).all()

    total_cost = 0
    cost_by_date = defaultdict(float)
    for res in reservations:
        if res.leaving_time and res.spot and res.spot.lot:
            date_str = res.parking_time.strftime('%d-%b')
            duration = (res.leaving_time - res.parking_time).total_seconds() / 3600
            duration = max(duration, 0.25)
            cost = round(duration * res.spot.lot.price, 2)
            total_cost += cost
            cost_by_date[date_str] += cost
            res.total_cost = cost
        else:
            res.total_cost = None

    return render_template('user_templates/reservation_history.html', reservations=reservations, timedelta=timedelta, total_cost=total_cost)

@user_bp.route('/summary')
@login_required
def reservation_summary():
    reservations = Reservation.query.filter_by(user_id=current_user.id).all()

    total_cost = 0
    cost_by_date = defaultdict(float)
    for res in reservations:
        if res.leaving_time and res.spot and res.spot.lot:
            date_str = res.parking_time.strftime('%d-%b')
            duration = (res.leaving_time - res.parking_time).total_seconds() / 3600
            duration = max(duration, 0.25)
            cost = round(duration * res.spot.lot.price, 2)
            total_cost += cost
            cost_by_date[date_str] += cost
            res.total_cost = cost
        else:
            res.total_cost = None

    summary = {
        'total_cost': round(total_cost, 2),
        'reservations': len(reservations)
    }

    return render_template('user_templates/reservation_summary.html', reservations=reservations, timedelta=timedelta, total_cost=total_cost, cost_by_date=cost_by_date, summary=summary)


@user_bp.route('/reserve/<int:lot_id>', methods=['POST'])
@login_required
def reserve_spot(lot_id):
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not spot:
        flash('No available spots in this lot.')
        return redirect(url_for('user.user_dashboard'))

    spot.status = 'O'
    reservation = Reservation(
        user_id=current_user.id,
        spot_id=spot.id,
        cost_per_hour=spot.lot.price 
    )
    db.session.add(reservation)
    db.session.commit()

    flash('Spot reserved successfully.')
    return redirect(url_for('user.user_dashboard'))

# @user_bp.route('/leave/<int:spot_id>')
# @login_required
# def leave_spot(spot_id):
#     spot = ParkingSpot.query.get(spot_id)
#     reservation = Reservation.query.filter_by(spot_id=spot_id, user_id=current_user.id).first()

#     if spot and reservation:
#         spot.status = 'A'
#         reservation.leaving_time = datetime.utcnow()
#         db.session.commit()

#         flash('Spot left successfully.')
    
#     else:
#         flash("No active reservation found")

#     return redirect(url_for('user.user_dashboard'))

@user_bp.route('/vacate/<int:reservation_id>', methods=['POST'])
@login_required
def vacate_spot(reservation_id): 
    reservation = Reservation.query.get_or_404(reservation_id)

    if reservation.user_id != current_user.id:
        flash("Unauthorized")
        return redirect(url_for("user.user_dashboard"))

    reservation.leaving_time = datetime.utcnow()
    hours = max((reservation.leaving_time - reservation.parking_time).total_seconds() / 3600, 1)
    total_price = round(hours * reservation.cost_per_hour, 2)

    spot = ParkingSpot.query.get(reservation.spot_id)
    spot.status = 'A'

    db.session.commit()
   
    flash(f'Spot vacated successfully. Total cost: ₹{total_price}')
    return redirect(url_for('user.user_dashboard'))