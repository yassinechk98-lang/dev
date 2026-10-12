(function(){
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Message après un clic sur « Télécharger »
  var toast = document.getElementById('dlToast'), toastTimer;
  document.querySelectorAll('.dl-link').forEach(function(a){
    a.addEventListener('click', function(){
      var help = document.createElement('a');
      help.href = '#avertissement';
      help.textContent = 'voici quoi faire';
      toast.replaceChildren('Téléchargement lancé. Si Windows bloque le fichier, ', help, '.');
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function(){ toast.classList.remove('show'); }, 8000);
    });
  });
  toast.addEventListener('click', function(e){
    if (e.target.tagName === 'A') toast.classList.remove('show');
  });

  // Ombre sous l'en-tête quand on défile
  var header = document.querySelector('header');
  function onScroll(){ header.classList.toggle('scrolled', window.scrollY > 8); }
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();

  // Apparition des blocs au défilement
  var items = document.querySelectorAll('.reveal');
  if (reduce || !('IntersectionObserver' in window)) {
    items.forEach(function(el){ el.classList.add('visible'); });
  } else {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); }
      });
    }, {threshold:0.15, rootMargin:'0px 0px -40px 0px'});
    items.forEach(function(el){ io.observe(el); });
  }

  // Lance une démo quand elle devient visible (ou affiche son état final)
  function startWhenVisible(el, cycle, showFinal){
    if (reduce || !('IntersectionObserver' in window)) { showFinal(); return; }
    var obs = new IntersectionObserver(function(entries){
      if (entries[0].isIntersecting) { obs.disconnect(); cycle(); }
    }, {threshold:0.3});
    obs.observe(el);
  }

  // Démo « Protection en temps réel » : des fichiers arrivent et sont analysés
  var rt = document.getElementById('rtDemo');
  if (rt) {
    var rtRows = rt.querySelectorAll('.rt-list li');
    var setSt = function(li, cls, text){ var st = li.querySelector('.st'); st.className = 'st ' + cls; st.textContent = text; };
    var rtFinal = function(){
      rtRows.forEach(function(li){ li.classList.add('in'); });
      setSt(rtRows[0], 'ok', 'Sain'); setSt(rtRows[1], 'ok', 'Sain');
      rtRows[2].classList.add('gone'); setSt(rtRows[2], 'danger', 'En quarantaine');
      rt.classList.add('alert');
    };
    var rtCycle = function(){
      rt.classList.remove('alert');
      rtRows.forEach(function(li){ li.classList.remove('in', 'bad', 'gone'); setSt(li, 'wait', 'Analyse…'); });
      [0, 1, 2].forEach(function(i){
        var t = 500 + i * 1300;
        setTimeout(function(){ rtRows[i].classList.add('in'); }, t);
        if (i < 2) setTimeout(function(){ setSt(rtRows[i], 'ok', 'Sain'); }, t + 800);
      });
      setTimeout(function(){ rtRows[2].classList.add('bad'); setSt(rtRows[2], 'danger', 'Menace'); }, 3900);
      setTimeout(function(){ rtRows[2].classList.add('gone'); setSt(rtRows[2], 'danger', 'En quarantaine'); rt.classList.add('alert'); }, 4800);
      setTimeout(rtCycle, 9000);
    };
    startWhenVisible(rt, rtCycle, rtFinal);
  }

  // Démo « Protection automatique » : les tâches du jour se cochent une à une
  var auto = document.getElementById('autoDemo');
  if (auto) {
    var autoRows = auto.querySelectorAll('.auto-list li');
    var autoFinal = function(){
      autoRows.forEach(function(li){ li.classList.remove('run'); li.classList.add('done'); });
      auto.classList.add('all');
    };
    var autoCycle = function(){
      auto.classList.remove('all');
      autoRows.forEach(function(li){ li.classList.remove('run', 'done'); });
      autoRows.forEach(function(li, i){
        var t = 600 + i * 1200;
        setTimeout(function(){ li.classList.add('run'); }, t);
        setTimeout(function(){ li.classList.remove('run'); li.classList.add('done'); }, t + 900);
      });
      setTimeout(function(){ auto.classList.add('all'); }, 600 + autoRows.length * 1200);
      setTimeout(autoCycle, 600 + autoRows.length * 1200 + 4000);
    };
    startWhenVisible(auto, autoCycle, autoFinal);
  }

  // Démo « Nouveautés » : bandeau, ClamAV en un clic, mise à jour de FreeAV
  var app = document.getElementById('appDemo');
  if (app) {
    var a = {};
    app.querySelectorAll('[data-a]').forEach(function(n){ a[n.getAttribute('data-a')] = n; });
    var later = function(ms, fn){ setTimeout(fn, ms); };
    var press = function(n){ n.classList.add('press'); later(300, function(){ n.classList.remove('press'); }); };
    var OK = 'Votre PC est protégé';
    var clamReady = function(){
      app.classList.remove('inst', 'fill');
      app.classList.add('clam-ok');
      a.clam.textContent = '+ ClamAV intégré : prêt';
      a.clamBtn.textContent = 'Mettre à jour ClamAV';
    };
    var appFinal = function(){
      app.classList.remove('warn');
      app.classList.add('upd');
      a.rt.classList.add('on');
      a.banner.textContent = OK;
      clamReady();
      a.note.textContent = 'Une nouvelle version de FreeAV est disponible';
    };
    var appCycle = function(){
      app.classList.remove('upd', 'clam-ok', 'inst', 'fill');
      app.classList.add('warn');
      a.rt.classList.remove('on');
      a.banner.textContent = 'Protection en temps réel désactivée';
      a.clam.textContent = '+ ClamAV intégré : non installé';
      a.clamBtn.textContent = 'Installer ClamAV (gratuit)';
      a.note.textContent = '';
      later(1200, function(){ press(a.rt); a.rt.classList.add('on'); app.classList.remove('warn'); a.banner.textContent = OK; });
      later(2800, function(){ press(a.clamBtn); });
      later(3150, function(){ app.classList.add('inst'); a.clam.textContent = '+ ClamAV : installation…'; });
      later(3250, function(){ app.classList.add('fill'); });
      later(5600, clamReady);
      later(7000, function(){ app.classList.add('upd'); a.note.textContent = 'Une nouvelle version de FreeAV est disponible'; });
      later(8400, function(){ press(a.upd); });
      later(8750, function(){ a.note.textContent = 'Téléchargement et vérification de la nouvelle version…'; });
      later(10300, function(){ app.classList.remove('upd'); a.note.textContent = 'FreeAV a redémarré : il est à jour'; });
      later(11900, function(){ press(a.quick); });
      later(12200, function(){ a.note.textContent = 'Analyse rapide en cours…'; });
      later(13900, function(){ a.note.textContent = 'Analyse rapide terminée : aucune menace'; });
      later(17000, appCycle);
    };
    startWhenVisible(app, appCycle, appFinal);
  }

  // Démo « Réparer mon PC » : diagnostic puis réparations, en boucle
  var rd = document.getElementById('repairDemo');
  if (rd) {
    var r = {};
    rd.querySelectorAll('[data-r]').forEach(function(n){ r[n.getAttribute('data-r')] = n; });
    var rows = rd.querySelectorAll('.rd-list li');
    var n = rows.length;
    var plural = function(k){ return k + (k > 1 ? ' problèmes' : ' problème'); };
    var at = function(ms, fn){ setTimeout(fn, ms); };
    var showFinal = function(){
      rows.forEach(function(li){ li.classList.add('on', 'fixed'); });
      rd.classList.add('done');
      r.status.textContent = 'Réparations terminées';
      r.count.textContent = plural(n);
      r.note.textContent = 'Sauvegarde créée, annulation possible';
    };
    var cycle = function(){
      rd.classList.remove('done');
      rows.forEach(function(li){ li.classList.remove('on', 'fixed'); });
      r.status.textContent = 'Diagnostic en cours…';
      r.count.textContent = '';
      r.note.textContent = "Rien n'a été modifié";
      var t = 400;
      rows.forEach(function(li, i){
        at(t + i * 650, function(){ li.classList.add('on'); r.count.textContent = plural(i + 1); });
      });
      t += n * 650 + 300;
      at(t, function(){
        rd.classList.add('done');
        r.status.textContent = 'Diagnostic terminé';
        r.note.textContent = plural(n) + " trouvés, rien n'a été modifié";
      });
      t += 1800;
      at(t, function(){ r.btn.classList.add('press'); });
      at(t + 350, function(){
        r.btn.classList.remove('press');
        rd.classList.remove('done');
        r.status.textContent = 'Réparation…';
        r.note.textContent = 'Réparation des problèmes choisis';
      });
      t += 600;
      rows.forEach(function(li, i){ at(t + i * 550, function(){ li.classList.add('fixed'); }); });
      t += n * 550 + 200;
      at(t, function(){
        rd.classList.add('done');
        r.status.textContent = 'Réparations terminées';
        r.note.textContent = 'Sauvegarde créée, annulation possible';
      });
      at(t + 4000, cycle);
    };
    if (reduce || !('IntersectionObserver' in window)) showFinal();
    else {
      var rdObs = new IntersectionObserver(function(entries){
        if (entries[0].isIntersecting) { rdObs.disconnect(); cycle(); }
      }, {threshold:0.3});
      rdObs.observe(rd);
    }
  }

  // Démo d'analyse en boucle
  var demo = document.getElementById('scanDemo');
  if (!demo) return;
  var el = {};
  demo.querySelectorAll('[data-k]').forEach(function(n){ el[n.getAttribute('data-k')] = n; });
  var files = [
    'C:\\Users\\Public\\Documents\\facture_2026.pdf',
    'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
    'C:\\Users\\Public\\Pictures\\vacances_042.jpg',
    'C:\\Users\\Public\\Downloads\\setup_jeu.exe',
    'C:\\Windows\\System32\\drivers\\etc\\hosts',
    'C:\\Users\\Public\\Music\\playlist.m3u',
    'C:\\Users\\Public\\Documents\\budget.xlsx',
    'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe',
    'C:\\Users\\Public\\Desktop\\notes.txt',
    'C:\\Users\\Public\\Videos\\anniversaire.mp4'
  ];
  var THREAT = 'C:\\Users\\Public\\Downloads\\eicar_test.com';
  var TOTAL = 1342, DURATION = 6500, HIT = 0.62;
  var fmt = function(n){ return n.toLocaleString('fr-FR'); };

  function render(p, found){
    el.pct.textContent = Math.floor(p * 100) + ' %';
    el.bar.style.transform = 'scaleX(' + p + ')';
    el.count.textContent = fmt(Math.floor(p * TOTAL));
    el.threats.textContent = found ? '1' : '0';
  }
  function finish(){
    demo.classList.add('done');
    el.status.textContent = 'Analyse terminée';
    el.file.textContent = fmt(TOTAL) + ' fichiers analysés, 1 menace isolée';
  }
  function run(){
    demo.classList.remove('done', 'alert');
    el.status.textContent = 'Analyse en cours…';
    var start = null, last = 0, i = 0, found = false;
    function frame(t){
      if (start === null) start = t;
      var p = Math.min((t - start) / DURATION, 1);
      if (!found && p >= HIT) {
        found = true;
        demo.classList.add('alert');
        el.file.textContent = THREAT;
      } else if (t - last > 110 && !(found && p < HIT + 0.1)) {
        last = t;
        el.file.textContent = files[i++ % files.length];
      }
      render(p, found);
      if (p < 1) requestAnimationFrame(frame);
      else { finish(); setTimeout(run, 3200); }
    }
    requestAnimationFrame(frame);
  }
  if (reduce) { render(1, true); demo.classList.add('alert'); finish(); }
  else run();
})();
