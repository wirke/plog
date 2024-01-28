function proveriSkladiste() {
    var skladisteSelect = document.getElementById('skladiste_id');
    var dugmePoruci = document.getElementById('dugmePoruci');
    if (skladisteSelect.value == '') {
        dugmePoruci.disabled = true;
    }
    else {
        dugmePoruci.disabled = false;
    }
}