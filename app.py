from flask import Flask, render_template, url_for, request, redirect, session
from flask_bcrypt import Bcrypt
import ast
import mysql.connector
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
app.secret_key = "tajni_kljuc_aplikacije"
bcrypt = Bcrypt(app)
#############################################################################
def ulogovan():
    if "ulogovani_korisnik" in session:
        return True
    else:
        return False
def rola():
    if ulogovan():
        return ast.literal_eval(session["ulogovani_korisnik"]).pop("rola")
#############################################################################
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        forma = request.form
        upit = "SELECT * FROM user WHERE email=%s"
        vrednost = (forma['emailPolje'],)
        candidate = request.form['passwordPolje']

        try:
            kursor.execute(upit, vrednost)
            user = kursor.fetchone()

            if user and bcrypt.check_password_hash(user['sifra'], candidate):
                session["ulogovani_korisnik"] = str(user)
                return redirect(url_for("pocetna"))
            else:
                return render_template("login.html", error="Nevalidni kredencijali")

        except Exception as e:
            print(f"Error: {e}")
            return render_template("login.html", error="Greska u logovanju")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        upit = """ INSERT INTO
        user(email, sifra, rola, lokacija)
        VALUES (%s, %s, %s, %s)
        """
        password = request.form['passwordPolje']
        pw_hash = bcrypt.generate_password_hash(password)
        forma = (request.form['emailPolje'], pw_hash, request.form['rola'], request.form['lokacijaPolje'])
        kursor.execute(upit,forma)
        konekcija.commit()
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.pop("ulogovani_korisnik", None)
    return redirect(url_for("login"))
#############################################################################
@app.route("/test", methods=['GET', 'POST'])
def test() -> html:
    if ulogovan() != True or rola() != 'Admin':
        return render_template("/greska.html")
    return render_template("/test.html")

@app.route("/pocetna", methods=['GET', 'POST'])
def pocetna() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin' or rola() != 'Proizvođač' or rola() != 'Logističar'):
        return render_template("/greska.html")
    return render_template("/pocetna.html")
#############################################################################
@app.route("/kupac/proizvodi", methods=['GET', 'POST'])
def prikaz_proizvoda() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/kupac/proizvodi.html")

@app.route("/kupac/proizvod", methods=['GET', 'POST'])
def naruci_proizvod() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/kupac/proizvod.html")

@app.route("/kupac/magacini", methods=['GET', 'POST'])
def prikaz_magacina() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/kupac/magacini.html")

@app.route("/kupac/magacin", methods=['GET', 'POST'])
def prelged_magacina() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/kupac/magacin.html")

@app.route("/kupac/porudzbine", methods=['GET', 'POST'])
def porudzbine_korisnik() -> html:
    if ulogovan() != True or (rola() != 'Kupac' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/kupac/porudzbine.html")
#############################################################################
@app.route("/proizvodjac/novi-proizvod", methods=['GET', 'POST'])
def novi_proizvod() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/novi-proizvod.html")

@app.route("/proizvodjac/moji-proizvodi", methods=['GET', 'POST'])
def porudzbine_proizvoda() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/moji-proizvodi.html")

@app.route("/proizvodjac/proizvod", methods=['GET', 'POST'])
def proizvod() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/proizvod.html")

@app.route("/proizvodjac/magacini", methods=['GET', 'POST'])
def pregledaj_magacine() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/magacini.html")

@app.route("/proizvodjac/magacin", methods=['GET', 'POST'])
def napuni_magacin() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/magacin.html")

@app.route("/proizvodjac/porudzbine", methods=['GET', 'POST'])
def pregledaj_porudzbine() -> html:
    if ulogovan() != True or (rola() != 'Proizvođač' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/proizvodjac/porudzbine.html")
#############################################################################
@app.route("/logisticar/moji-magacini", methods=['GET', 'POST'])
def moji_magacina() -> html:
    if ulogovan() != True or (rola() != 'Logističar' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/logisticar/moji-magacini.html")

@app.route("/logisticar/magacin", methods=['GET', 'POST'])
def magacin() -> html:
    if ulogovan() != True or (rola() != 'Logističar' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/logisticar/magacin.html")

@app.route("/logisticar/novi-magacin", methods=['GET', 'POST'])
def novi_magacin() -> html:
    if ulogovan() != True or (rola() != 'Logističar' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/logisticar/novi-magacin.html")

@app.route("/logisticar/porudzbine", methods=['GET', 'POST'])
def porudzbina_magacin() -> html:
    if ulogovan() != True or (rola() != 'Logističar' or rola() != 'Admin'):
        return render_template("/greska.html")
    return render_template("/logisticar/porudzbine.html")

app.run(debug=True)