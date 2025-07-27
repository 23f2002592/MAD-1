from flask import Blueprint, render_template, redirect, url_for, request, flash
from app import db
from flask_login import login_required, current_user, login_user, logout_user
from app.models import User, ParkingLot, ParkingSpot, Reservation
from flask_login import login_required, current_user
from datetime import timedelta
from collections import defaultdict

admin_bp = Blueprint('admin', __name__)
def is_not_admin():
    return getattr(current_user, 'role', '') != 'admin'

@admin_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if getattr(current_user, 'role', '') != 'admin':
        logout_user()
        flash('Access denied. Admins only.')
        return redirect(url_for('user.login'))

    users = User.query.filter(User.role != 'admin').all()
    lots = ParkingLot.query.all()

    total_lots = len(lots)
    total_spots = sum(len(lot.spots) for lot in lots)
    occupied_spots = sum(1 for lot in lots for spot in lot.spots if spot.status == 'O')
    available_spots = total_spots - occupied_spots

    spot_reservations = {}
    for lot in lots:
        for spot in lot.spots:
            reservation = Reservation.query.filter_by(spot_id=spot.id).order_by(Reservation.parking_time.desc()).first()
            if reservation:
                spot_reservations[spot.id] = reservation

    return render_template('admin_templates/dashboard_admin.html', users=users, lots=lots, spot_reservation=spot_reservations, timedelta=timedelta)

@admin_bp.route('/admin/users')
@login_required
def view_users():
    if is_not_admin():
        flash('Access denied.')
        return redirect(url_for('user.login'))
    
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin_templates/view_users.html', users=users)

@admin_bp.route('/admin/summary', methods=['GET', 'POST'])
@login_required
def admin_summary():
    if is_not_admin():
        flash('Access denied.')
        return redirect(url_for('user.login'))
    
    lots = ParkingLot.query.all()

    total_lots = len(lots)
    total_spots = sum(len(lot.spots) for lot in lots)
    occupied_spots = sum(1 for lot in lots for spot in lot.spots if spot.status == 'O')
    available_spots = total_spots - occupied_spots

    summary = {
        'total_lots': total_lots,
        'total_spots': total_spots,
        'occupied_spots': occupied_spots,
        'available_spots': available_spots
    }

    return render_template('admin_templates/admin_summary.html', summary=summary)
    

@admin_bp.route('/admin/add_lot', methods=['GET', 'POST'])
@login_required
def add_lot():
    if getattr(current_user, 'role', '') != 'admin':
        flash('Access denied.')
        return redirect(url_for('user.login'))

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        address = request.form['address']
        pin = request.form['pin']
        max_spots = int(request.form['max_spots'])

        new_lot = ParkingLot(
            location_name=name,
            price=price,
            address=address,
            pin_code=pin,
            max_spots=max_spots
        )
        db.session.add(new_lot)
        db.session.commit()

        for i in range(1, max_spots+1):
            spot = ParkingSpot(lot_id=new_lot.id, status='A', spot_number = i) 
            db.session.add(spot)
        db.session.commit()

        flash('Parking lot and spots added successfully.')
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('admin_templates/manage_lots.html')

@admin_bp.route('/admin/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def edit_lot(lot_id):
    if is_not_admin():
        flash('Access denied.')
        return redirect(url_for('user.login'))

    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        lot.location_name = request.form['name']
        lot.price = float(request.form['price'])
        lot.address = request.form['address']
        lot.pin_code = request.form['pin']
        new_max_spots = int(request.form['max_spots'])

        existing_spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        existing_numbers = [s.spot_number for s in existing_spots]
        existing_count = len(existing_numbers)
        max_existing = max(existing_numbers) if existing_numbers else 0

        occupied_spots = [spot for spot in existing_spots if spot.status != 'A']
        if occupied_spots and new_max_spots != existing_count:
            flash('⚠️ Cannot edit spots while some spots are occupied.')
            return redirect(url_for('admin.admin_dashboard'))

        if new_max_spots > existing_count:
            for i in range(1, new_max_spots - existing_count + 1):
                new_spot = ParkingSpot(lot_id=lot.id, status="A", spot_number=max_existing + i)
                db.session.add(new_spot)
        elif new_max_spots < existing_count:
            extra_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').order_by(ParkingSpot.spot_number.desc()).all()
            to_delete_count = existing_count - new_max_spots
            deleted = 0
            for spot in extra_spots:
                if deleted >= to_delete_count:
                    break
                db.session.delete(spot)
                deleted += 1

        lot.max_spots = new_max_spots
        db.session.commit()
        flash('Parking lot updated successfully.')

        return redirect(url_for('admin.admin_dashboard'))
    
    return render_template('admin_templates/manage_lots.html', lot=lot)

@admin_bp.route('/admin/delete_lot/<int:lot_id>', methods=['GET'])
@login_required
def delete_lot(lot_id):
    if is_not_admin():
        flash('Access denied.')
        return redirect(url_for('user.login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)

    occupied_spots = any(spot.status == 'O' for spot in lot.spots)
    if occupied_spots:
        flash('⚠️ Cannot delete lot with occupied spots.')
        return redirect(url_for('admin.admin_dashboard'))

    for spot in lot.spots:
        db.session.delete(spot)

    db.session.delete(lot)
    db.session.commit()

    flash('Parking lot deleted succesffully.')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/view_reservations')
@login_required
def view_reservations():
    if is_not_admin():
        flash('Access denied.')
        return redirect(url_for('user.login'))

    reservations = Reservation.query.order_by(Reservation.parking_time.desc()).all()

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

    return render_template('admin_templates/view_reservations.html', reservations=reservations, timedelta=timedelta, total_cost=total_cost)
