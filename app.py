import os
import uuid
from datetime import datetime
from functools import wraps

import requests
from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///travel.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# API CONFIGURATION
# =========================================================

AMADEUS_BASE_URL = os.getenv(
    "AMADEUS_BASE_URL",
    "https://test.api.amadeus.com"
)

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")


# =========================================================
# DATABASE MODELS
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    bookings = db.relationship(
        "Booking",
        backref="user",
        lazy=True
    )

    def set_password(self, password):

        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):

        return check_password_hash(
            self.password_hash,
            password
        )


class Booking(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    booking_reference = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    origin = db.Column(
        db.String(10),
        nullable=False
    )

    destination = db.Column(
        db.String(10),
        nullable=False
    )

    travel_date = db.Column(
        db.String(20),
        nullable=False
    )

    airline = db.Column(
        db.String(100)
    )

    departure_time = db.Column(
        db.String(20)
    )

    arrival_time = db.Column(
        db.String(20)
    )

    price = db.Column(
        db.String(30)
    )

    status = db.Column(
        db.String(30),
        default="Confirmed"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# LOGIN DECORATOR
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for(
                    "login"
                )
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# AMADEUS API
# =========================================================

def get_amadeus_token():

    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:

        return None

    response = requests.post(

        f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",

        data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_CLIENT_ID,
            "client_secret": AMADEUS_CLIENT_SECRET
        },

        timeout=15
    )

    response.raise_for_status()

    return response.json()["access_token"]


def search_flights_api(
    origin,
    destination,
    travel_date,
    adults
):

    token = get_amadeus_token()

    if not token:

        return None

    response = requests.get(

        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",

        headers={
            "Authorization": f"Bearer {token}"
        },

        params={

            "originLocationCode": origin,

            "destinationLocationCode": destination,

            "departureDate": travel_date,

            "adults": adults,

            "currencyCode": "INR",

            "max": 10
        },

        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# DEMO DATA
# =========================================================

def demo_flights(
    origin,
    destination,
    date
):

    return [

        {
            "id": "DEMO001",
            "airline": "IndiGo",
            "origin": origin,
            "destination": destination,
            "departure": "08:30",
            "arrival": "10:45",
            "duration": "2h 15m",
            "price": "₹6,499",
            "date": date
        },

        {
            "id": "DEMO002",
            "airline": "Air India",
            "origin": origin,
            "destination": destination,
            "departure": "12:15",
            "arrival": "14:40",
            "duration": "2h 25m",
            "price": "₹7,199",
            "date": date
        },

        {
            "id": "DEMO003",
            "airline": "Vistara",
            "origin": origin,
            "destination": destination,
            "departure": "18:20",
            "arrival": "20:30",
            "duration": "2h 10m",
            "price": "₹8,250",
            "date": date
        }
    ]


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form["name"].strip()

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return render_template(
                "register.html"
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already registered.",
                "danger"
            )

            return render_template(
                "register.html"
            )

        user = User(
            name=name,
            email=email
        )

        user.set_password(password)

        db.session.add(user)

        db.session.commit()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.check_password(password):

            session.clear()

            session["user_id"] = user.id

            session["user_name"] = user.name

            flash(
                "Login successful!",
                "success"
            )

            return redirect(
                url_for("search")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Logged out successfully.",
        "info"
    )

    return redirect(
        url_for("index")
    )


# =========================================================
# SEARCH
# =========================================================

@app.route(
    "/search",
    methods=["GET", "POST"]
)
@login_required
def search():

    flights = []

    searched = False

    form_data = {

        "origin": "",

        "destination": "",

        "date": "",

        "adults": 1
    }

    data_source = "Demo data"

    if request.method == "POST":

        origin = request.form[
            "origin"
        ].strip().upper()

        destination = request.form[
            "destination"
        ].strip().upper()

        date = request.form[
            "date"
        ]

        adults = int(
            request.form.get(
                "adults",
                1
            )
        )

        form_data = {

            "origin": origin,

            "destination": destination,

            "date": date,

            "adults": adults
        }

        searched = True

        try:

            api_data = search_flights_api(

                origin,

                destination,

                date,

                adults
            )

            if api_data:

                data_source = "Live Amadeus API"

                for offer in api_data.get(
                    "data",
                    []
                ):

                    itinerary = offer[
                        "itineraries"
                    ][0]

                    segments = itinerary[
                        "segments"
                    ]

                    first_segment = segments[0]

                    last_segment = segments[-1]

                    flights.append({

                        "id": offer["id"],

                        "airline":
                            offer.get(
                                "validatingAirlineCodes",
                                ["Airline"]
                            )[0],

                        "origin": origin,

                        "destination": destination,

                        "departure":
                            first_segment[
                                "departure"
                            ]["at"][11:16],

                        "arrival":
                            last_segment[
                                "arrival"
                            ]["at"][11:16],

                        "duration":
                            itinerary[
                                "duration"
                            ],

                        "price":
                            f"₹{float(offer['price']['total']):,.0f}",

                        "date": date
                    })

            else:

                flights = demo_flights(
                    origin,
                    destination,
                    date
                )

        except Exception as error:

            print(
                "API ERROR:",
                error
            )

            flash(
                "Live API unavailable. Showing demo flights.",
                "warning"
            )

            flights = demo_flights(
                origin,
                destination,
                date
            )

    return render_template(

        "search.html",

        flights=flights,

        searched=searched,

        form_data=form_data,

        data_source=data_source
    )


# =========================================================
# BOOK FLIGHT
# =========================================================

@app.route(
    "/book",
    methods=["POST"]
)
@login_required
def book():

    reference = (
        "TRV-"
        + uuid.uuid4().hex[:8].upper()
    )

    booking = Booking(

        user_id=session["user_id"],

        booking_reference=reference,

        origin=request.form["origin"],

        destination=request.form["destination"],

        travel_date=request.form["date"],

        airline=request.form["airline"],

        departure_time=request.form["departure"],

        arrival_time=request.form["arrival"],

        price=request.form["price"],

        status="Confirmed"
    )

    db.session.add(booking)

    db.session.commit()

    flash(
        f"Booking confirmed! Reference: {reference}",
        "success"
    )

    return redirect(
        url_for("bookings")
    )


# =========================================================
# MY BOOKINGS
# =========================================================

@app.route("/bookings")
@login_required
def bookings():

    user_bookings = Booking.query.filter_by(

        user_id=session["user_id"]

    ).order_by(

        Booking.created_at.desc()

    ).all()

    return render_template(

        "bookings.html",

        bookings=user_bookings
    )


# =========================================================
# JSON SEARCH API
# =========================================================

@app.route("/api/search")
@login_required
def api_search():

    origin = request.args.get(
        "origin",
        ""
    ).upper()

    destination = request.args.get(
        "destination",
        ""
    ).upper()

    date = request.args.get(
        "date",
        ""
    )

    if not origin or not destination or not date:

        return jsonify({

            "error":
                "Origin, destination and date are required."

        }), 400

    try:

        data = search_flights_api(

            origin,

            destination,

            date,

            1
        )

        if data:

            return jsonify(data)

    except Exception as error:

        print(error)

    return jsonify({

        "demo": True,

        "data": demo_flights(

            origin,

            destination,

            date
        )

    })


# =========================================================
# DATABASE
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )