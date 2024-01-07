from flask import Flask, render_template, url_for, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import mysql.connector
import mariadb
import json
import html

konekcija = mysql.connector.connect(
    passwd='2578',
    user='root',
    database='plog',
    port=3306,
    auth_plugin='mysql_native_password',
)

kursor = konekcija.cursor(dictionary=True)
app = Flask(__name__)
#############################################################################
@app.route("/test", methods=['GET', 'POST'])
def test() -> html:
    return render_template("/folder/temp.html")
#############################################################################
@app.route("/login", methods=['GET', 'POST'])
def login() -> html:
    return render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register() -> html:
    return render_template("register.html")
#############################################################################
@app.route("/korisnik", methods=['GET', 'POST'])
def korisnik() -> html:
    return render_template("/korisnik/korisnik.html")

@app.route("/prikaz-proizvoda", methods=['GET', 'POST'])
def prikaz_proizvoda() -> html:
    return render_template("/korisnik/prikaz-proizvoda.html")

@app.route("/pregled-proizvod", methods=['GET', 'POST'])
def naruci_proizvod() -> html:
    return render_template("/korisnik/pregled-proizvod.html")

@app.route("/prikaz-magacina", methods=['GET', 'POST'])
def prikaz_magacina() -> html:
    return render_template("/korisnik/prikaz-magacina.html")

@app.route("/pregled-magacin", methods=['GET', 'POST'])
def prelged_magacina() -> html:
    return render_template("/korisnik/pregled-magacin.html")

@app.route("/porudzbine-korisnik", methods=['GET', 'POST'])
def porudzbine_korisnik() -> html:
    return render_template("/korisnik/porudzbine-korisnik.html")
#############################################################################
@app.route("/proizvodjac", methods=['GET', 'POST'])
def proizvodjac() -> html:
    return render_template("/proizvodjac/proizvodjac.html")

@app.route("/novi-proizvod", methods=['GET', 'POST'])
def novi_proizvod() -> html:
    return render_template("/proizvodjac/novi-proizvod.html")

@app.route("/prikazi-proizvode", methods=['GET', 'POST'])
def porudzbine_proizvoda() -> html:
    return render_template("/proizvodjac/prikazi-proizvode.html")

@app.route("/proizvod", methods=['GET', 'POST'])
def proizvod() -> html:
    return render_template("/proizvodjac/proizvod.html")

@app.route("/prikazi-magacine", methods=['GET', 'POST'])
def pregledaj_magacine() -> html:
    return render_template("/proizvodjac/prikazi-magacine.html")

@app.route("/napuni-magacin", methods=['GET', 'POST'])
def napuni_magacin() -> html:
    return render_template("/proizvodjac/napuni-magacin.html")

@app.route("/prikazi-porudzbine", methods=['GET', 'POST'])
def pregledaj_porudzbine() -> html:
    return render_template("/proizvodjac/prikazi-porudzbine.html")

@app.route("/porudzbina", methods=['GET', 'POST'])
def porudzbina() -> html:
    return render_template("/proizvodjac/porudzbina.html")
#############################################################################
@app.route("/logisticar", methods=['GET', 'POST'])
def logisticar() -> html:
    return render_template("/logisticar/logisticar.html")

@app.route("/moji-magacini", methods=['GET', 'POST'])
def moji_magacina() -> html:
    return render_template("/logisticar/moji-magacini.html")

@app.route("/magacin", methods=['GET', 'POST'])
def magacin() -> html:
    return render_template("/logisticar/magacin.html")

@app.route("/novi-magacin", methods=['GET', 'POST'])
def novi_magacin() -> html:
    return render_template("/logisticar/novi-magacin.html")

@app.route("/porudzbine-logisticar", methods=['GET', 'POST'])
def porudzbine_logisticar() -> html:
    return render_template("/logisticar/porudzbine-logisticar.html")

@app.route("/porudzbine", methods=['GET', 'POST'])
def porudzbina_magacin() -> html:
    return render_template("/logisticar/porudzbine.html")

app.run(debug=True)