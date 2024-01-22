from flask import Flask, render_template, url_for, request, redirect, session
from flask_bcrypt import Bcrypt
from datetime import datetime
from functools import wraps
import mysql.connector
import html
#############################################################################
konekcija = mysql.connector.connect(
    passwd='',
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
    return 'korisnik_id' in session

def rola():
    return session.get('rola', None) if ulogovan() else None

@app.context_processor
def utility_log():
    return dict(ulogovan=ulogovan)

@app.context_processor
def utility_role():
    return dict(rola=rola)

@app.context_processor
def inject_user_data():
    user_data = None
    if ulogovan():
        korisnik_id = session.get('korisnik_id')
        upit = "SELECT * FROM user WHERE id = %s"
        kursor.execute(upit, (korisnik_id,))
        korisnik = kursor.fetchone()
        user_data = korisnik if korisnik else None
    return dict(user_data=user_data)
#############################################################################
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        forma = request.form
        upit = "SELECT * FROM user WHERE email=%s"
        email = (forma['emailPolje'],)
        sifra = request.form['passwordPolje']

        try:
            kursor.execute(upit, email)
            user = kursor.fetchone()

            if user and bcrypt.check_password_hash(user['sifra'], sifra):
                print(f"Uspesno logovanje. Email: {user['email']}")
                session['korisnik_id'] = user['id']
                session['rola'] = user['rola']
                return redirect(url_for('pocetna'))
            else:
                print("Neuspelo logovanje. Email:", forma['emailPolje'])
                print("Hash iz baze:", user['sifra'])
                return redirect(url_for('greska'))
            
        except Exception as e:
            print(f"Error: {e}")
            return redirect(url_for('greska'))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    
    elif request.method == "POST":
        existing_email_check = "SELECT * FROM user WHERE email=%s"
        existing_email = (request.form['emailPolje'],)
        kursor.execute(existing_email_check, existing_email)
        existing_user = kursor.fetchone()

        if existing_user:
            return render_template("register.html", error="Mejl je već u upotrebi.")
        upit = """ INSERT INTO
        user(email, ime, sifra, rola, lokacija)
        VALUES (%s, %s, %s, %s, %s)
        """
        password = request.form['passwordPolje']
        pw_hash = bcrypt.generate_password_hash(password)
        forma = (request.form['emailPolje'], request.form['imePolje'], pw_hash, request.form['rola'], request.form['lokacijaPolje'])
        kursor.execute(upit,forma)
        konekcija.commit()
        return redirect(url_for("login"))
    
@app.route("/logout")
def logout():
    session.pop('korisnik_id', None)
    session.pop('rola', None)
    return redirect(url_for('login'))
#############################################################################
def zahteva_dozvolu(roles=[]):
    def omotac(f):
        @wraps(f)
        def omotana_funkcija(*args, **kwargs):
            if ulogovan():
                trenutna_rola = rola()
                if not roles or trenutna_rola in roles:
                    return f(*args, **kwargs)
            return redirect(url_for('greska'))
        return omotana_funkcija
    return omotac

def zahteva_ulogovanje(f):
    @wraps(f)
    def omotana_funkcija(*args, **kwargs):
        if ulogovan():
            return f(*args, **kwargs)
        return redirect(url_for('greska'))
    return omotana_funkcija

@app.route("/greska", methods=['GET', 'POST'])
def greska() -> html:
    return render_template("/greska.html")
#############################################################################
@app.route("/test", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin'])
def test() -> html:
    return render_template("/test.html")

@app.route("/pocetna", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač', 'Logističar', 'Kupac'])
def pocetna() -> html:
    return render_template("/pocetna.html")
#############################################################################
def get_proizvod(proizvod_id: int) -> dict:
    upit_proizvod = """
        SELECT p.id, p.ime, p.kategorija, p.cena, p.proizvodjac_id, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE p.id = %s
    """
    kursor.execute(upit_proizvod, (proizvod_id,))
    proizvod = kursor.fetchone()
    return proizvod

def svi_proizvodi() -> dict:
    upit_proizvodi = """
        SELECT id, ime, kategorija, cena
        FROM proizvod
    """
    kursor.execute(upit_proizvodi)
    proizvodi = kursor.fetchall()
    return proizvodi

def proveri_dostupnost_kolicine(proizvod_id, skladiste_id, kolicina):
    upit_dostupnost = """
        SELECT ps.kolicina
        FROM sadrzi ps
        WHERE ps.proizvod_id = %s AND ps.skladiste_id = %s
    """
    kursor.execute(upit_dostupnost, (proizvod_id, skladiste_id))
    dostupna_kolicina = kursor.fetchone()

    return dostupna_kolicina['kolicina'] if dostupna_kolicina else 0

def get_skladiste(skladiste_id: int) -> dict:
    upit_skladiste = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE s.id = %s
    """
    kursor.execute(upit_skladiste, (skladiste_id,))
    skladiste = kursor.fetchone()
    return skladiste

def sva_skladista() -> dict:
    upit_skladista = """
        SELECT s.id, s.ime AS skladiste_ime, s.kapacitet, s.lokacija, l.ime AS logisticar_ime
        FROM skladiste s
        LEFT JOIN user l ON s.logisticar_id = l.id
    """
    kursor.execute(upit_skladista)
    skladista = kursor.fetchall()
    return skladista

def get_porudzbinu() -> dict:
    korisnik_id = session.get('korisnik_id')

    upit_porudzbine = """
        SELECT p.id, p.datum, p.kolicina, p.isporuceno, p.kategorija, p.kupac_id, p.proizvodjac_id, p.skladiste_id, s.ime AS skladiste_ime
        FROM porudzbina p
        JOIN skladiste s ON p.skladiste_id = s.id
        WHERE p.kupac_id = %s
    """
    kursor.execute(upit_porudzbine, (korisnik_id,))
    porudzbina = kursor.fetchone()
    return porudzbina

def sve_porudzbine() -> dict:
    upit_porudzbine = """
        SELECT id, datum, kolicina, isporuceno, kategorija, kupac_id, proizvodjac_id, skladiste_id
        FROM porudzbina
    """
    kursor.execute(upit_porudzbine)
    porudzbine = kursor.fetchall()
    return porudzbine
#############################################################################
@app.route("/kupac/proizvodi", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikaz_proizvoda() -> html:

    odabrana_kategorija = request.args.get('kategorija', '')
    odabrano_sortiranje = request.args.get('sortiranje', 'asc')

    upit_kategorije = "SELECT DISTINCT kategorija FROM proizvod"
    kursor.execute(upit_kategorije)
    sve_kategorije = [red['kategorija'] for red in kursor.fetchall()]

    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE (%s = '' OR p.kategorija = %s)
        ORDER BY p.cena {0}
    """.format(odabrano_sortiranje)

    kursor.execute(upit_proizvoda, (odabrana_kategorija, odabrana_kategorija))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/proizvodi.html", proizvodi=proizvodi, sve_kategorije=sve_kategorije, odabrana_kategorija=odabrana_kategorija, odabrano_sortiranje=odabrano_sortiranje)

@app.route("/kupac/proizvod/<int:proizvod_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def kupi_proizvod(proizvod_id: int) -> html:

    odabrana_kategorija = request.args.get('kategorija', '')
    odabrano_sortiranje = request.args.get('sortiranje', 'asc')

    upit_skladista = """
        SELECT s.id, s.ime AS skladiste_ime, s.lokacija
        FROM proizvod p
        JOIN sadrzi ps ON p.id = ps.proizvod_id
        JOIN skladiste s ON ps.skladiste_id = s.id
        WHERE p.id = %s
    """
    kursor.execute(upit_skladista, (proizvod_id,))
    skladista = kursor.fetchall()

    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE (%s = '' OR p.kategorija = %s)
        ORDER BY p.cena {0}
    """.format(odabrano_sortiranje)

    kursor.execute(upit_proizvoda, (odabrana_kategorija, odabrana_kategorija))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/proizvod.html", skladista=skladista, proizvodi=proizvodi, odabrana_kategorija=odabrana_kategorija, odabrano_sortiranje=odabrano_sortiranje)

@app.route("/kupac/magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikaz_magacina() -> html:

    odabrana_lokacija = request.args.get('lokacija', '')
    upit_lokacija = "SELECT DISTINCT lokacija FROM skladiste"
    kursor.execute(upit_lokacija)
    sve_lokacije = [red['lokacija'] for red in kursor.fetchall()]

    upit_skladista = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE s.lokacija = %s
    """.format(odabrana_lokacija)

    kursor.execute(upit_skladista, (odabrana_lokacija, ))
    skladista = kursor.fetchall()

    return render_template("/kupac/magacini.html", skladista=skladista, sve_lokacije=sve_lokacije, odabrana_lokacija=odabrana_lokacija)

@app.route("/kupac/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikazi_magacin(skladiste_id: int) -> html:

    skladiste = get_skladiste(skladiste_id)
    upit_proizvoda = """
        SELECT id, ime, kategorija, cena, ime AS proizvod_ime
        FROM proizvod
        JOIN sadrzi ON proizvod.id = sadrzi.proizvod_id
        WHERE sadrzi.skladiste_id = %s
    """
    kursor.execute(upit_proizvoda, (skladiste_id,))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/magacin.html", skladiste=skladiste, proizvodi=proizvodi)

@app.route("/kupac/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def porudzbine_korisnik() -> html:
    return render_template("/kupac/porudzbine.html")
#############################################################################
@app.route("/proizvodjac/novi-proizvod", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def novi_proizvod() -> html:
    return render_template("/proizvodjac/novi-proizvod.html")

@app.route("/proizvodjac/moji-proizvodi", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def porudzbine_proizvoda() -> html:
    return render_template("/proizvodjac/moji-proizvodi.html")

@app.route("/proizvodjac/proizvod", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def proizvod() -> html:
    return render_template("/proizvodjac/proizvod.html")

@app.route("/proizvodjac/magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def pregledaj_magacine() -> html:
    return render_template("/proizvodjac/magacini.html")

@app.route("/proizvodjac/magacin", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def napuni_magacin() -> html:
    return render_template("/proizvodjac/magacin.html")

@app.route("/proizvodjac/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def pregledaj_porudzbine() -> html:
    return render_template("/proizvodjac/porudzbine.html")
#############################################################################
@app.route("/logisticar/moji-magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def moji_magacina() -> html:
    return render_template("/logisticar/moji-magacini.html")

@app.route("/logisticar/magacin", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def magacin() -> html:
    return render_template("/logisticar/magacin.html")

@app.route("/logisticar/novi-magacin", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def novi_magacin() -> html:
    if request.method == "GET":
        return render_template("/logisticar/novi-magacin.html")
    elif request.method == "POST":
        upit = """
        INSERT INTO skladiste(logisticar_id, ime, kapacitet, lokacija)
        VALUES (%s, %s, %s, %s)
        """
        forma = (session['korisnik_id'], request.form['magacinNaziv'], request.form['magacinKapacitet'], request.form['magacinLokacija'])
        kursor.execute(upit, forma)
        konekcija.commit()
        return redirect(url_for("novi_magacin"))

@app.route("/logisticar/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def porudzbina_magacin() -> html:
    return render_template("/logisticar/porudzbine.html")

if __name__ == "__main__":
    app.run(debug=True)