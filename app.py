from flask import Flask, render_template, url_for, request, redirect, session, flash, Response
from flask_bcrypt import Bcrypt
from datetime import datetime
from functools import wraps
import mysql.connector
import html
import io
import csv
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

@app.errorhandler(404)
def not_found(error):
    flash('Nepostojeća stranica!')
    return redirect(url_for('greska'))

@app.route("/greska", methods=['GET', 'POST'])
def greska():
    return render_template('greska.html')
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
                session['korisnik_id'] = user['id']
                session['rola'] = user['rola']
                return redirect(url_for('pocetna'))
            else:
                flash('Pogrešni kredencijali')
                return redirect(url_for('greska'))
            
        except Exception as e:
            flash('Došlo je do greške!')
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
            flash('Kredencijali koje ste uneli su zauzeti!')
            return render_template("greska.html")
        
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
@app.route("/admin/korisnici", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin'])
def pregled_korisnika() -> html:
    
    if request.method == 'GET':
        upit = """SELECT id, email, ime, rola, lokacija
                  FROM user"""
        kursor.execute(upit)
        korisnici = kursor.fetchall()

    elif request.method == 'POST':
        if 'izbrisi_korisnika' in request.form:
            korisnik_id = request.form['izbrisi_korisnika']
            izbrisi = """
                DELETE FROM user
                WHERE id = %s
            """
            kursor.execute(izbrisi, (korisnik_id,))
            konekcija.commit()
            flash("Korisnik uspešno izbrisan!")
            return redirect(url_for('pregled_korisnika'))
        
    return render_template("/admin/korisnici.html", korisnici=korisnici)

@app.route("/admin/export/<tip>")
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin'])
def export(tip):
    switch = {
        "skladiste": "SELECT * FROM skladiste",
        "proizvod": "SELECT * FROM proizvod",
        "porudzbina": "SELECT * FROM porudzbina",
    }
    upit = switch.get(tip)
    kursor.execute(upit)
    rezultat = kursor.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rezultat:
        red = []
        for value in row.values():
            red.append(str(value))
        writer.writerow(red)

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=" + tip + ".csv"},
    )
#############################################################################
@app.route("/pocetna", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač', 'Logističar', 'Kupac'])
def pocetna() -> html:

    korisnik_id = session.get('korisnik_id')
    if session['rola'] == 'Kupac':

        upit_porudzbine = """
            SELECT COUNT(*) AS ukupno_porudzbina, SUM(CASE WHEN isporuceno = 0 THEN 1 ELSE 0 END) AS neisporuceno
            FROM porudzbina
            WHERE kupac_id = %s
        """
        kursor.execute(upit_porudzbine, (korisnik_id,))
        rezultat = kursor.fetchone()
        ukupno_porudzbina = rezultat['ukupno_porudzbina']
        neisporuceno = rezultat['neisporuceno']
        return render_template("/pocetna.html", ukupno_porudzbina=ukupno_porudzbina, neisporuceno=neisporuceno)

    elif session['rola'] == 'Proizvođač':

        upit_proizvoda = """
            SELECT COUNT(DISTINCT p.id) AS ukupno_proizvoda, COUNT(DISTINCT p.kategorija) AS ukupno_kategorija
            FROM proizvod p
            WHERE p.proizvodjac_id = %s;
        """
        kursor.execute(upit_proizvoda, (korisnik_id,))
        rezultat = kursor.fetchone()
        ukupno_proizvoda = rezultat['ukupno_proizvoda']
        ukupno_kategorija = rezultat['ukupno_kategorija']
        return render_template("/pocetna.html", ukupno_proizvoda=ukupno_proizvoda, ukupno_kategorija=ukupno_kategorija)
    
    elif session['rola'] == 'Logističar':
        
        upit_skladista = """
        SELECT l.id AS logisticar_id, COUNT(DISTINCT s.id) AS ukupno_skladista, COUNT(DISTINCT s.lokacija) AS ukupno_gradova
        FROM user l
        JOIN skladiste s ON l.id = s.logisticar_id
        WHERE s.logisticar_id = %s;
        """
        kursor.execute(upit_skladista, (korisnik_id,))
        rezultat = kursor.fetchone()
        ukupno_skladista = rezultat['ukupno_skladista']
        ukupno_gradova = rezultat['ukupno_gradova']
        return render_template("/pocetna.html", ukupno_gradova=ukupno_gradova, ukupno_skladista=ukupno_skladista)
    
    elif session['rola'] == 'Admin':
        
        upit = """
            SELECT COUNT(*) AS ukupno_korisnika
            FROM user;
        """
        kursor.execute(upit,)
        rezultat = kursor.fetchone()
        ukupno_korisnika = rezultat['ukupno_korisnika']
        return render_template("/pocetna.html", ukupno_korisnika=ukupno_korisnika)

    else:
        flash('KAKO?')
        return render_template("/greska.html")
#############################################################################
@app.route("/izmena-naloga", methods=["GET","POST"])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač', 'Logističar', 'Kupac'])
def izmena_korisnika():
    
    if request.method == "GET":
        return render_template("/izmeni_korisnika.html")
    
    stara_sifra = request.form.get('pwPolje')
    novi_password = request.form.get('pwNoviPolje')

    upit_stare_sifre = "SELECT sifra FROM user WHERE id = %s"
    kursor.execute(upit_stare_sifre, (session['korisnik_id'],))
    rezultat = kursor.fetchone()

    if not rezultat or not bcrypt.check_password_hash(rezultat['sifra'], stara_sifra):
        flash("Uneli ste pogrešnu šifru!")
        return redirect(url_for('greska'))

    upit = """UPDATE user
        SET ime = %s, sifra = %s, lokacija = %s
        WHERE id = %s
    """
    pw_hash = bcrypt.generate_password_hash(novi_password)
    forma = (request.form['imePolje'], pw_hash, request.form['lokacijaPolje'], session['korisnik_id'])
    kursor.execute(upit, forma)
    konekcija.commit()
    return redirect(url_for('pocetna'))
#############################################################################
@app.route("/kupac/proizvodi", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikaz_proizvoda() -> html:

    odabrana_kategorija = request.args.get('kategorija', '')
    odabrano_sortiranje = request.args.get('sortiranje', 'asc')
    odabrani_proizvodjac = request.args.get('proizvodjac', '')

    upit_kategorije = "SELECT DISTINCT kategorija FROM proizvod"
    kursor.execute(upit_kategorije)
    sve_kategorije = [red['kategorija'] for red in kursor.fetchall()]

    upit_proizvodjaci = "SELECT id, ime FROM user WHERE rola = 'Proizvođač'"
    kursor.execute(upit_proizvodjaci)
    svi_proizvodjaci = kursor.fetchall()

    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE (%s = '' OR p.kategorija = %s) AND (%s = '' OR p.proizvodjac_id = %s)
        ORDER BY p.cena {0}
    """.format(odabrano_sortiranje)
    kursor.execute(upit_proizvoda, (odabrana_kategorija, odabrana_kategorija, odabrani_proizvodjac, odabrani_proizvodjac))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/proizvodi.html", proizvodi=proizvodi, sve_kategorije=sve_kategorije, svi_proizvodjaci=svi_proizvodjaci, odabrana_kategorija=odabrana_kategorija, odabrano_sortiranje=odabrano_sortiranje)

@app.route("/kupac/proizvod/<int:proizvod_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def kupi_proizvod(proizvod_id: int) -> html:
    
    upit_skladista = """
        SELECT s.id, s.ime, s.lokacija, u.ime AS logisticar_ime, ps.kolicina AS kolicina_proizvoda
        FROM skladiste s
        JOIN sadrzi ps ON s.id = ps.skladiste_id
        JOIN proizvod p ON ps.proizvod_id = p.id
        JOIN user u ON s.logisticar_id = u.id
        WHERE p.id = %s
    """
    kursor.execute(upit_skladista, (proizvod_id,))
    skladista = kursor.fetchall()

    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE p.id = %s
    """
    kursor.execute(upit_proizvoda, (proizvod_id,))
    proizvod = kursor.fetchall()

    return render_template("/kupac/proizvod.html", skladista=skladista, proizvod=proizvod)

@app.route("/kupac/magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikaz_magacina() -> html:
    odabrana_lokacija = request.args.get('lokacija', '')
    
    upit_lokacija = "SELECT DISTINCT lokacija FROM skladiste"
    kursor.execute(upit_lokacija)
    sve_lokacije = [red['lokacija'] for red in kursor.fetchall()]

    if odabrana_lokacija:
        upit_skladista = """
            SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime, 
            COALESCE(SUM(sa.kolicina), 0) AS popunjenost
            FROM skladiste s
            JOIN user u ON s.logisticar_id = u.id
            LEFT JOIN sadrzi sa ON s.id = sa.skladiste_id
            WHERE s.lokacija = %s
            GROUP BY s.id
        """
        kursor.execute(upit_skladista, (odabrana_lokacija,))
    else:
        upit_skladista = """
            SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime, 
            COALESCE(SUM(sa.kolicina), 0) AS popunjenost
            FROM skladiste s
            JOIN user u ON s.logisticar_id = u.id
            LEFT JOIN sadrzi sa ON s.id = sa.skladiste_id
            GROUP BY s.id
        """
        kursor.execute(upit_skladista)

    skladiste = kursor.fetchall()

    return render_template("/kupac/magacini.html", skladiste=skladiste, sve_lokacije=sve_lokacije, odabrana_lokacija=odabrana_lokacija)

@app.route("/kupac/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikazi_magacin(skladiste_id: int) -> html:

    odabrano_sortiranje = request.args.get('sortiranje', 'asc')
    kategorija = request.args.get('kategorija', '')

    upit_kategorije = """
        SELECT DISTINCT p.kategorija 
        FROM proizvod p 
        JOIN sadrzi s ON p.id = s.proizvod_id 
        WHERE s.skladiste_id = %s
    """
    kursor.execute(upit_kategorije, (skladiste_id,))
    sve_kategorije = [red['kategorija'] for red in kursor.fetchall()]

    upit_skladista = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE s.id = %s
    """
    kursor.execute(upit_skladista, (skladiste_id,))
    skladiste = kursor.fetchone()

    upit_proizvodi = """
        SELECT p.id, p.ime, p.kategorija, p.cena, proizvodjac.ime AS proizvodjac_ime, s.kolicina AS broj_proizvoda
        FROM proizvod p
        JOIN sadrzi s ON p.id = s.proizvod_id
        JOIN user proizvodjac ON p.proizvodjac_id = proizvodjac.id
        WHERE s.skladiste_id = %s AND (%s = '' OR p.kategorija = %s)
        ORDER BY p.cena {0}
    """.format(odabrano_sortiranje)
    kursor.execute(upit_proizvodi, (skladiste_id, kategorija, kategorija,))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/magacin.html", skladiste=skladiste, proizvodi=proizvodi, odabrano_sortiranje=odabrano_sortiranje, kategorija=kategorija, sve_kategorije=sve_kategorije)

@app.route("/kupac/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def porudzbine_korisnik() -> html:
    
    korisnik_id = session.get('korisnik_id')
    isporuceno = request.args.get('isporuceno', '')
    datum = request.args.get('datum', 'desc')

    if isporuceno is None:
        isporuceno = ''

    upit_porudzbina = """
        SELECT p.id AS porudzbina_id, DATE_FORMAT(p.datum, '%d-%m-%Y') AS d_datum, p.kolicina, p.isporuceno, pr.cena, pr.kategorija AS proizvod_kategorija, 
        pr.ime AS proizvod_ime,u_proizvodjac.ime AS proizvodjac_ime, s.ime AS skladiste_ime, u_kupac.ime AS kupac_ime
        FROM porudzbina p
        JOIN user u_kupac ON p.kupac_id = u_kupac.id
        JOIN proizvod pr ON p.proizvod_id = pr.id
        JOIN user u_proizvodjac ON pr.proizvodjac_id = u_proizvodjac.id
        JOIN skladiste s ON p.skladiste_id = s.id
        WHERE p.kupac_id = %s AND (p.isporuceno = %s OR %s = '')
        ORDER BY p.datum {0}
    """.format(datum)
    kursor.execute(upit_porudzbina, (korisnik_id, isporuceno, isporuceno))
    porudzbine = kursor.fetchall()
        
    if postoji_porudzbina(korisnik_id):
        return render_template("/kupac/porudzbine.html", porudzbine=porudzbine)
    else:
        return render_template("/kupac/porudzbine.html")

def postoji_porudzbina(korisnik_id):
    upit = """
        SELECT COUNT(*) AS broj_porudzbina
        FROM porudzbina p
        JOIN user u_kupac ON p.kupac_id = u_kupac.id
        JOIN proizvod pr ON p.proizvod_id = pr.id
        JOIN user u_proizvodjac ON pr.proizvodjac_id = u_proizvodjac.id
        JOIN skladiste s ON p.skladiste_id = s.id
        WHERE kupac_id = %s
    """
    kursor.execute(upit, (korisnik_id,))
    rezultat = kursor.fetchone()
    
    if rezultat['broj_porudzbina'] > 0:
        return True
    else:
        return False

@app.route('/kupac/poruci_proizvod/<int:proizvod_id>', methods=['POST', 'GET'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def poruci_proizvod(proizvod_id):
    
    if request.method == 'POST':
        skladiste_id = request.form.get('skladiste_id')
        kolicina = request.form.get('kolicina')
        korisnik_id = session.get('korisnik_id')
        napomena = request.form.get('napomena')

        upit_kolicine = "SELECT kolicina FROM sadrzi WHERE skladiste_id = %s AND proizvod_id = %s"
        kursor.execute(upit_kolicine, (skladiste_id, proizvod_id))
        trenutna_kolicina = kursor.fetchone()

        if trenutna_kolicina and int(kolicina) <= trenutna_kolicina['kolicina']:
            dodaj_porudzbinu = """
            INSERT INTO porudzbina (datum, kolicina, isporuceno, napomena, kupac_id, proizvod_id, skladiste_id)
            VALUES (CURDATE(), %s, 0, %s, %s, %s, %s)
            """
            kursor.execute(dodaj_porudzbinu, (kolicina, napomena, korisnik_id, proizvod_id, skladiste_id))
            konekcija.commit()

            nova_kolicina = trenutna_kolicina['kolicina'] - int(kolicina)
            azuriraj_kolicinu = "UPDATE sadrzi SET kolicina = %s WHERE skladiste_id = %s AND proizvod_id = %s"
            kursor.execute(azuriraj_kolicinu, (nova_kolicina, skladiste_id, proizvod_id))
            konekcija.commit()

            return redirect(url_for('porudzbine_korisnik'))
        else:
            flash('Niste popunili sve parametre!')
            return redirect(url_for('greska'))
    else:
        return redirect(url_for('greska', poruka='Proizvod nije dostupan!'))
#############################################################################
@app.route("/proizvodjac/novi-proizvod", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def novi_proizvod() -> html:
    if request.method == "GET":
        return render_template("/proizvodjac/novi-proizvod.html")
    
    if request.method == "POST":
        upit = """INSERT INTO proizvod(proizvodjac_id, ime, kategorija, opis, cena)
        VALUES (%s, %s, %s, %s, %s)
        """
        forma = (session['korisnik_id'], request.form['proizvodIme'], request.form['kategorijaIme'], request.form['proizvodOpis'], request.form['proizvodCena'])
        kursor.execute(upit, forma)
        konekcija.commit()
        return redirect(url_for("moji_proizvodi"))

@app.route("/proizvodjac/moji-proizvodi", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def moji_proizvodi() -> html:
    
    if(postoji_proizvod):
        upit= """
        SELECT id, ime, kategorija, cena, opis
        FROM proizvod
        WHERE proizvodjac_id = %s
        """
        kursor.execute(upit, (session['korisnik_id'],))
        proizvodi = kursor.fetchall()
        return render_template("/proizvodjac/moji-proizvodi.html", proizvodi=proizvodi)

@app.route("/proizvodjac/brisanje-proizvoda/<int:proizvod_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def brisanje_proizvoda(proizvod_id) -> html:
    
    upit = """
    DELETE FROM proizvod
    WHERE id = %s
    """
    kursor.execute(upit, (proizvod_id,))
    konekcija.commit()
    return redirect(url_for('moji_proizvodi'))

def postoji_proizvod(korisnik_id):
    
    korisnik_id = (session['korisnik_id'])
    upit = """
        SELECT COUNT(*) AS broj_proizvoda
        FROM proizvod p
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE p.proizvodjac_id = %s
    """
    kursor.execute(upit, (korisnik_id,))
    rezultat = kursor.fetchone()
    if rezultat['broj_proizvoda'] > 0:
        return True
    else:
        return False

@app.route("/proizvodjac/proizvod/<int:proizvod_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def proizvod(proizvod_id) -> html:
    
    if request.method == 'GET':
        upit_pr= """
        SELECT p.id, p.ime, p.kategorija, p.cena, p.opis
        FROM proizvod p
        WHERE p.id = %s
        """
        kursor.execute(upit_pr, (proizvod_id,))
        proizvod = kursor.fetchone()

        upit_mag = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija
        FROM skladiste s
        JOIN sadrzi sd ON s.id=sd.skladiste_id
        WHERE sd.proizvod_id NOT %s
        """
        kursor.execute(upit_mag, (proizvod_id,))
        skladiste = kursor.fetchall()

        upit_sva_skladista = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, s.kapacitet - COALESCE(SUM(sr.kolicina), 0) AS dostupan_kapacitet
        FROM skladiste s
        LEFT JOIN sadrzi sr ON s.id = sr.skladiste_id
        WHERE sr.proizvod_id IS NULL OR sr.proizvod_id != %s
        """
        kursor.execute(upit_sva_skladista, (proizvod_id,))
        sva_skladista= kursor.fetchall()

    if request.method == "POST":
        if 'azuriraj_proizvod' in request.form:
            upit = """UPDATE proizvod
            SET ime= %s, kategorija= %s, cena= %s, opis = %s
            WHERE id = %s
            """
            vrednosti = (request.form['prIme'], request.form['prKategorija'],request.form['prCena'],request.form['prOpis'], proizvod_id)
            kursor.execute(upit, vrednosti)
            konekcija.commit()
            return redirect(url_for('prenos', proizvod_id=proizvod_id))

        elif 'dodavanje' in request.form:
            kap_mag = """
            SELECT s.id, s.ime, s.kapacitet - COALESCE(SUM(sd.kolicina), 0) AS dostupni_kapacitet, s.lokacija
            FROM skladiste s
            LEFT JOIN sadrzi sd ON s.id = sd.skladiste_id
            WHERE s.id = %s
            """
            kursor.execute(kap_mag, (request.form.get('izabrano_skl'),))
            rezultat = kursor.fetchone()
            dostupni_kapacitet = int(rezultat['dostupni_kapacitet'])
            
            if int(request.form.get('kolicina')) <= dostupni_kapacitet:
                upit = """INSERT INTO
                sadrzi (proizvod_id, skladiste_id, kolicina)
                VALUES (%s, %s, %s)
                """
                kursor.execute(upit, (proizvod_id, request.form.get('izabrano_skl'), request.form.get('kolicina'),))
                konekcija.commit()
                return redirect(url_for('prenos', proizvod_id=proizvod_id))

            else:
                flash('Proizvod prelazi dostupnu kolicinu magacina')
                return redirect(url_for('greska'))

        elif 'brisanje_iz_skladista' in request.form:
            skladiste_id = request.form['skladiste_id']
            izbrisi_proizvod_iz_skladista(proizvod_id, skladiste_id, kursor, konekcija)
            return redirect(url_for('prenos', proizvod_id=proizvod_id))

    return render_template("/proizvodjac/proizvod.html", proizvod=proizvod, skladiste=skladiste, sva_skladista=sva_skladista)

@app.route("/proizvodjac/redirect/<int:proizvod_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def prenos(proizvod_id):
    return redirect(url_for('proizvod', proizvod_id=proizvod_id))

@app.route("/proizvodjac/magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def pregledaj_magacine() -> html:
    upit = """SELECT id, ime, lokacija, kapacitet
    FROM skladiste"""
    kursor.execute(upit)
    skladista = kursor.fetchall()
    return render_template("/proizvodjac/magacini.html",skladista=skladista)

@app.route("/proizvodjac/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def napuni_magacin(skladiste_id: int) -> html:
    upit = """SELECT s.id, s.ime, s.kapacitet, s.lokacija
    FROM skladiste s
    WHERE id = %s
    """
    kursor.execute(upit, (skladiste_id,))
    skladiste = kursor.fetchone()

    upit_pro = """SELECT p.id, p.ime, p.cena, p.kategorija
    FROM proizvod p
    JOIN sadrzi sd ON p.id=sd.proizvod_id
    WHERE sd.skladiste_id = %s
    """
    kursor.execute(upit_pro, (skladiste_id,))
    proizvodi = kursor.fetchall()
    return render_template("/proizvodjac/magacin.html", skladiste=skladiste, proizvodi=proizvodi)

@app.route("/proizvodjac/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def pregledaj_porudzbine() -> html:
    
    upit = """SELECT po.kolicina AS kolicina, pr.ime AS ime_proizvoda, pr.cena AS cena, po.isporuceno AS isporuceno, u.ime AS ime, u.lokacija AS lokacija
    FROM porudzbina po
    JOIN proizvod pr ON pr.id=po.proizvod_id
    JOIN user u ON u.id=po.kupac_id
    WHERE pr.proizvodjac_id = %s
    """
    kursor.execute(upit, (session['korisnik_id'],))
    porudzbine = kursor.fetchall()
    return render_template("/proizvodjac/porudzbine.html", porudzbine=porudzbine)
#############################################################################
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
        return redirect(url_for("moji_magacini"))

@app.route("/logisticar/moji-magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def moji_magacini() -> html:

    if request.method == 'POST':
        if 'izbrisi' in request.form:
            skladiste_id = request.form['izbrisi_magacin']
            brisanje_magacina(skladiste_id, kursor, konekcija)
            return redirect(url_for('magacin', skladiste_id=skladiste_id))

    upit = """
    SELECT s.id, s.ime, s.lokacija, s.kapacitet, SUM(ps.kolicina) AS popunjenost
    FROM skladiste s
    LEFT JOIN sadrzi ps ON s.id = ps.skladiste_id
    WHERE s.logisticar_id = %s
    GROUP BY s.id
    """
    kursor.execute(upit, (session['korisnik_id'],))
    skladiste = kursor.fetchall()

    return render_template("/logisticar/moji-magacini.html", skladiste=skladiste)

@app.route("/logisticar/brisanje-skladista/<int:id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Logističar'])
def brisanje_magacina(id) -> html:
    
    upit = """
    DELETE FROM skladiste
    WHERE id = %s
    """
    kursor.execute(upit, (id,))
    konekcija.commit()
    return redirect(url_for('moji_magacini'))

@app.route("/logisticar/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Logističar'])
def magacin(skladiste_id: int) -> html:

    upit_skladiste = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime, SUM(ps.kolicina) AS popunjenost
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        LEFT JOIN sadrzi ps ON s.id = ps.skladiste_id
        WHERE s.id = %s
    """
    kursor.execute(upit_skladiste, (skladiste_id,))
    skladiste = kursor.fetchone()
        
    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, ps.kolicina, u.ime AS proizvodjac_ime
        FROM proizvod p
        JOIN sadrzi ps ON p.id = ps.proizvod_id
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE ps.skladiste_id = %s
    """
    kursor.execute(upit_proizvoda, (skladiste_id,))
    proizvodi = kursor.fetchall()

    if request.method == "POST":
        if 'azuriraj_kapacitet' in request.form:
            nova_vrednost = int(request.form['nova_vrednost'])
            azuriraj_kapacitet(skladiste_id, nova_vrednost, kursor, konekcija)
            return redirect(url_for('magacin', skladiste_id=skladiste_id))

        elif 'izbrisi_proizvod' in request.form:
            proizvod_id = request.form['izbrisi_proizvod']
            izbrisi_proizvod_iz_skladista(proizvod_id, skladiste_id, kursor, konekcija)
            return redirect(url_for('magacin', skladiste_id=skladiste_id))

        elif 'izmeni_kolicinu' in request.form:
            proizvod_id_za_izmenu = int(request.form['proizvod_id'])
            nova_kolicina = int(request.form['nova_kolicina'])
            azuriraj_kolicinu_proizvoda(proizvod_id_za_izmenu, skladiste_id, nova_kolicina, kursor, konekcija)
            return redirect(url_for('magacin', skladiste_id=skladiste_id))

    return render_template("/logisticar/magacin.html", skladiste_id=skladiste_id, skladiste=skladiste, proizvodi=proizvodi)

def azuriraj_kolicinu_proizvoda(proizvod_id:int, skladiste_id:int, nova_kolicina, kursor, konekcija):
    upit_dostupnosti = """
        SELECT SUM(ps.kolicina) AS popunjenost, s.kapacitet
        FROM sadrzi ps
        JOIN skladiste s ON ps.skladiste_id = s.id
        WHERE ps.skladiste_id = %s
        GROUP BY s.kapacitet
    """
    kursor.execute(upit_dostupnosti, (skladiste_id,))
    dostupnost = kursor.fetchone()

    if dostupnost:
        trenutni_kapacitet = dostupnost['kapacitet']
        trenutna_popunjenost = dostupnost['popunjenost']

        if nova_kolicina <= trenutni_kapacitet - trenutna_popunjenost:
            upit_azuriranja = """
                UPDATE sadrzi
                SET kolicina = %s
                WHERE proizvod_id = %s AND skladiste_id = %s
            """
            kursor.execute(upit_azuriranja, (nova_kolicina, proizvod_id, skladiste_id))
            konekcija.commit()
            print('uspesno')
            return redirect(url_for('magacin', skladiste_id=skladiste_id)), True
        else:
            flash("Nova količina proizvoda premašuje trenutni kapacitet")
            return redirect(url_for('greska'))

def izbrisi_proizvod_iz_skladista(proizvod_id:int, skladiste_id:int, kursor, konekcija):
    upit_brisanja = """
        DELETE FROM sadrzi
        WHERE proizvod_id = %s AND skladiste_id = %s
    """
    kursor.execute(upit_brisanja, (proizvod_id, skladiste_id))
    konekcija.commit()

def azuriraj_kapacitet(skladiste_id:int, nova_vrednost:int, kursor, konekcija):
    upit_popunjenosti = """
        SELECT SUM(ps.kolicina) AS popunjenost
        FROM sadrzi ps
        WHERE ps.skladiste_id = %s
    """
    kursor.execute(upit_popunjenosti, (skladiste_id,))
    trenutna_popunjenost = kursor.fetchone()['popunjenost'] or 0

    if nova_vrednost >= trenutna_popunjenost:
        upit_azuriranja = """
            UPDATE skladiste
            SET kapacitet = %s
            WHERE id = %s
        """
        kursor.execute(upit_azuriranja, (nova_vrednost, skladiste_id))
        konekcija.commit()
        return redirect(url_for('magacin', skladiste_id=skladiste_id))
    else:
        flash("Uneti kapacitet je manji od trenutne popunjenosti!")
        return redirect(url_for('greska'))

@app.route("/logisticar/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Logističar'])
def porudzbina_magacin():
    korisnik_id = session.get('korisnik_id')
    isporuceno = request.args.get('isporuceno')
    datum = request.args.get('datum', 'asc')

    if isporuceno is None:
        isporuceno = ''

    upit_porudzbina = """
    SELECT p.id AS porudzbina_id, DATE_FORMAT(p.datum, '%d-%m-%Y') AS d_datum, p.kolicina, p.napomena, p.isporuceno, pr.cena, pr.kategorija AS proizvod_kategorija, 
    pr.ime AS proizvod_ime, u_proizvodjac.ime AS proizvodjac_ime, s.ime AS skladiste_ime, s.lokacija AS skladiste_lokacija, u_kupac.ime AS kupac_ime, uk.lokacija AS kupac_lokacija
    FROM porudzbina p
    JOIN user u_kupac ON p.kupac_id = u_kupac.id
    JOIN proizvod pr ON p.proizvod_id = pr.id
    JOIN user u_proizvodjac ON pr.proizvodjac_id = u_proizvodjac.id
    JOIN skladiste s ON p.skladiste_id = s.id
    JOIN user uk ON p.kupac_id = uk.id
    WHERE s.logisticar_id = %s AND (p.isporuceno = %s OR %s = '')
    ORDER BY p.datum {0}
    """.format(datum)

    kursor.execute(upit_porudzbina, (korisnik_id, isporuceno, isporuceno))
    porudzbina = kursor.fetchall()

    return render_template("/logisticar/porudzbine.html", porudzbina=porudzbina)

@app.route("/logisticar/isporuci/<int:porudzbina_id>", methods=['POST'])
def isporuci(porudzbina_id):
    
    isporuceno = request.form.get('isporuceno')
    upit_azuriranja = """
    UPDATE porudzbina
    SET isporuceno = %s
    WHERE id = %s
    """
    kursor.execute(upit_azuriranja, (isporuceno, porudzbina_id))
    konekcija.commit()

    return redirect(url_for('porudzbina_magacin'))

if __name__ == "__main__":
    app.run(debug=True)