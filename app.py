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

    upit_skladista = """
        SELECT s.id, s.ime, s.lokacija, u.ime AS logisticar_ime
        FROM proizvod p
        JOIN sadrzi ps ON p.id = ps.proizvod_id
        JOIN skladiste s ON ps.skladiste_id = s.id
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

    upit_skladista = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE (%s = '' OR s.lokacija = %s)
    """
    kursor.execute(upit_skladista, (odabrana_lokacija, odabrana_lokacija))
    skladiste = kursor.fetchall()

    return render_template("/kupac/magacini.html", skladiste=skladiste, sve_lokacije=sve_lokacije, odabrana_lokacija=odabrana_lokacija)

@app.route("/kupac/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def prikazi_magacin(skladiste_id) -> html:

    upit_skladiste = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE s.id = %s
    """
    kursor.execute(upit_skladiste, (skladiste_id,))
    skladiste = kursor.fetchone()

    cena_max = request.args.get('cena_max', '')
    cena_min = request.args.get('cena_min', '')
    odabrano_sortiranje = request.args.get('sortiranje', '')
    kategorija = request.args.get('kategorija', '')
    
    upit_kategorija = """
        SELECT DISTINCT p.kategorija
        FROM skladiste s
        JOIN sadrzi sa ON s.id = sa.skladiste_id
        JOIN proizvod p ON sa.proizvod_id = p.id
        WHERE s.id = %s
    """
    kursor.execute(upit_kategorija, (skladiste_id,))
    kategorija = kursor.fetchall()

    upit_proizvodi = """
        SELECT p.id, p.ime, p.kategorija, p.cena, u.ime AS proizvodjac_ime
        FROM skladiste s
        JOIN sadrzi sa ON s.id = sa.skladiste_id
        JOIN proizvod p ON sa.proizvod_id = p.id
        JOIN user u ON p.proizvodjac_id = u.id
        WHERE s.id = %s AND (%s IS NULL OR p.cena <= %s) AND (%s IS NULL OR p.cena >= %s) AND (%s IS NULL OR p.kategorija = %s)
        ORDER BY p.cena %s
    """
    kursor.execute(upit_proizvodi, (skladiste_id, cena_max, cena_max, cena_min, cena_min, kategorija, kategorija, odabrano_sortiranje,))
    proizvodi = kursor.fetchall()

    return render_template("/kupac/magacin.html", skladiste=skladiste, kategorija=kategorija, proizvodi=proizvodi, cena_max=cena_max, cena_min=cena_min, odabrano_sortiranje=odabrano_sortiranje)

@app.route("/kupac/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def porudzbine_korisnik() -> html:
    korisnik_id = session.get('korisnik_id')

    prikaz_porudzbina = """
    SELECT p.id AS porudzbina_id, p.datum, p.kolicina, p.isporuceno, pr.cena, pr.kategorija AS proizvod_kategorija, u_proizvodjac.ime AS proizvodjac_ime, s.ime AS skladiste_ime, u_kupac.ime AS kupac_ime
    FROM porudzbina p
    JOIN user u_kupac ON p.kupac_id = u_kupac.id
    JOIN proizvod pr ON p.proizvod_id = pr.id
    JOIN user u_proizvodjac ON pr.proizvodjac_id = u_proizvodjac.id
    JOIN skladiste s ON p.skladiste_id = s.id
    WHERE kupac_id = %s
    """
    kursor.execute(prikaz_porudzbina, (korisnik_id,))
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

@app.route("/poruci_proizvod/<int:proizvod_id>", methods=['POST', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Kupac'])
def poruci_proizvod(proizvod_id):
    if request.method == 'POST':

        skladiste_id = request.form.get('skladiste')
        kolicina = request.form.get('kolicina')
        korisnik_id = session['korisnik_id']

        dodaj_porudzbinu = """
            INSERT INTO porudzbina (datum, kolicina, isporuceno, kategorija, kupac_id, proizvod_id, skladiste_id)
            VALUES (CURRENT_DATE(), %s, 0, (SELECT kategorija FROM proizvod WHERE id = %s), %s, %s, %s)
        """
        kursor.execute(dodaj_porudzbinu, (kolicina, proizvod_id, korisnik_id, proizvod_id, skladiste_id))
        konekcija.commit()

        return redirect(url_for('porudzbine'))
#############################################################################
@app.route("/proizvodjac/novi-proizvod", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def novi_proizvod() -> html:

    if request.method == "GET":
        return render_template("/proizvodjac/novi-proizvod.html")
    upit = """INSERT INTO proizvod(proizvodjac_id, ime, kategorija, cena, kolicina)
    VALUES (%s, %s, %s, %s, %s)
    """
    forma = (session['korisnik_id'], request.form['proizvodIme'], request.form['kategorijaIme'], request.form['proizvodCena'], request.form['proizvodKolicina'])
    kursor.execute(upit, forma)
    konekcija.commit()
    return redirect(url_for("novi_proizvod"))

@app.route("/proizvodjac/moji-proizvodi", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def porudzbine_proizvoda() -> html:
    upit= """
    SELECT ime, kategorija, cena, kolicina
    FROM proizvod
    WHERE proizvodjac_id = %s
    """
    kursor.execute(upit, (session['korisnik_id'],))
    proizvodi = kursor.fetchall()
    return render_template("/proizvodjac/moji-proizvodi.html", proizvodi=proizvodi)

@app.route("/proizvodjac/proizvod", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def proizvod() -> html:
    return render_template("/proizvodjac/proizvod.html")

@app.route("/proizvodjac/magacini", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Proizvođač'])
def pregledaj_magacine() -> html:
    upit = """SELECT ime, lokacija, kapacitet
    FROM skladiste"""
    kursor.execute(upit)
    skladista = kursor.fetchall()
    return render_template("/proizvodjac/magacini.html",skladista=skladista)

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
def moji_magacini() -> html:
    upit = """
    SELECT id, ime, lokacija, kapacitet
    FROM skladiste
    WHERE logisticar_id = %s
    """
    kursor.execute(upit, (session['korisnik_id'],))
    skladista = kursor.fetchall()
    return render_template("/logisticar/moji-magacini.html",skladista=skladista)

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
    
@app.route("/logisticar/magacin/<int:skladiste_id>", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def magacin(skladiste_id: int) -> html:

    upit_skladiste = """
        SELECT s.id, s.ime, s.kapacitet, s.lokacija, u.ime AS logisticar_ime
        FROM skladiste s
        JOIN user u ON s.logisticar_id = u.id
        WHERE s.id = %s
    """
    kursor.execute(upit_skladiste, (skladiste_id,))
    skladiste = kursor.fetchone()

    upit_proizvoda = """
        SELECT p.id, p.ime, p.kategorija, p.cena, ps.kolicina
        FROM proizvod p
        JOIN sadrzi ps ON p.id = ps.proizvod_id
        WHERE ps.skladiste_id = %s
    """
    kursor.execute(upit_proizvoda, (skladiste_id,))
    proizvodi = kursor.fetchall()

    if request.method == "POST":
        if 'azuriraj_kapacitet' in request.form:
            nova_vrednost = int(request.form['nova_vrednost'])
            if azuriraj_kapacitet_skladista(skladiste_id, nova_vrednost):
                print("Uspesno azuriranje")
            else:
                print("Greska prilikom azuriranja")
        
        elif 'izbrisi_proizvod' in request.form:
            proizvod_id_za_brisanje = int(request.form['izbrisi_proizvod'])
            izbrisi_proizvod_iz_skladista(proizvod_id_za_brisanje, skladiste_id)

        elif 'izmeni_kolicinu' in request.form:
            proizvod_id_za_izmenu = int(request.form['izmeni_kolicinu'])
            nova_kolicina = int(request.form['nova_kolicina'])
            azuriraj_kolicinu_proizvoda_u_skladistu(proizvod_id_za_izmenu, skladiste_id, nova_kolicina)
    return render_template("/logisticar/magacin.html", skladiste=skladiste, proizvodi=proizvodi)

def azuriraj_kolicinu_proizvoda_u_skladistu(proizvod_id, skladiste_id, nova_kolicina):
    dostupna_kolicina = proveri_dostupnost_kolicine(proizvod_id, skladiste_id, nova_kolicina)
    if nova_kolicina >= dostupna_kolicina:
        upit = """
            UPDATE sadrzi
            SET kolicina = %s
            WHERE proizvod_id = %s AND skladiste_id = %s
        """
        kursor.execute(upit, (nova_kolicina, proizvod_id, skladiste_id))
        konekcija.commit()
        return True
    else:
        return False

def izbrisi_proizvod_iz_skladista(proizvod_id, skladiste_id):
    upit_izbrisi = """
        DELETE FROM sadrzi
        WHERE proizvod_id = %s AND skladiste_id = %s
    """
    kursor.execute(upit_izbrisi, (proizvod_id, skladiste_id))
    konekcija.commit()

def azuriraj_kapacitet_skladista(skladiste_id, nova_vrednost):
    upit_azuriraj_kapacitet = """
        UPDATE skladiste
        SET kapacitet = %s
        WHERE id = %s
    """
    kursor.execute(upit_azuriraj_kapacitet, (nova_vrednost, skladiste_id))
    konekcija.commit()

def proveri_kapacitet_skladista(skladiste_id: int) -> bool:
    upit_popunjenost = """
        SELECT SUM(ps.kolicina) AS popunjenost
        FROM sadrzi ps
        WHERE ps.skladiste_id = %s
    """
    kursor.execute(upit_popunjenost, (skladiste_id,))
    popunjenost = kursor.fetchone()['popunjenost'] or 0
    
    upit_kapacitet = """
        SELECT kapacitet
        FROM skladiste
        WHERE id = %s
    """
    kursor.execute(upit_kapacitet, (skladiste_id,))
    kapacitet = kursor.fetchone()['kapacitet']

    return popunjenost <= kapacitet

def azuriraj_kapacitet_skladista(skladiste_id, nova_vrednost):
    if proveri_kapacitet_skladista(skladiste_id):
        upit_azuriraj_kapacitet = """
            UPDATE skladiste
            SET kapacitet = %s
            WHERE id = %s
        """
        kursor.execute(upit_azuriraj_kapacitet, (nova_vrednost, skladiste_id))
        konekcija.commit()
        return True
    else:
        return False
    
def proveri_dostupnost_kolicine(proizvod_id, skladiste_id, kolicina):
    upit_dostupnost = """
        SELECT ps.kolicina
        FROM sadrzi ps
        WHERE ps.proizvod_id = %s AND ps.skladiste_id = %s
    """
    kursor.execute(upit_dostupnost, (proizvod_id, skladiste_id))
    dostupna_kolicina = kursor.fetchone()

    return dostupna_kolicina['kolicina'] if dostupna_kolicina else 0

@app.route("/logisticar/porudzbine", methods=['GET', 'POST'])
@zahteva_ulogovanje
@zahteva_dozvolu(roles=['Admin', 'Logističar'])
def porudzbina_magacin() -> html:

    return render_template("/logisticar/porudzbine.html")

if __name__ == "__main__":
    app.run(debug=True)