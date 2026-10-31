(function () {
  'use strict';
  var preview = new URLSearchParams(window.location.search).get('preview') === '1';
  var notice = document.getElementById('notice');
  var cover = document.getElementById('sleep-cover');
  var clockTime = document.getElementById('clock-time');
  var clockDate = document.getElementById('clock-date');
  var ports = window.HDMI_PORTS || {};
  var portIds = ['hdmi1', 'hdmi3', 'hdmi4'];
  var portIcons = ['port', 'pc', 'controller', 'media'];
  var dimTimer, sleepTimer, noticeTimer, launchTimer, clockTimer;
  var bridge = null;
  var busy = false;
  var launching = null;
  var sleeping = false;
  var alive = true;
  // Fixed recovery command only; no user input or network content enters a shell.
  var stockHomeCommand = 'if [ -f /var/lib/lg-hdmi-home-router/home-router.py ]; then python3 /var/lib/lg-hdmi-home-router/home-router.py stock-home; else luna-send -n 1 luna://com.webos.applicationManager/launch \'{"id":"com.webos.app.home"}\'; fi';

  function unused(id) {
    return Boolean(ports[id] && ports[id].unused);
  }

  // Port names, icons and unused flags come from ports.js; HDMI 2 is always the Xbox tile.
  portIds.forEach(function (id) {
    var config = ports[id] || {};
    var button = document.getElementById(id);
    if (!button) return;
    if (config.unused) { button.hidden = true; return; }
    if (config.name) {
      button.querySelector('.secondary-label').textContent = button.getAttribute('data-label');
      button.querySelector('strong').textContent = config.name;
      button.setAttribute('data-label', config.name);
    }
    // An icon only says something once the port is named, so unnamed ports show none.
    if (config.name && portIcons.indexOf(config.icon) !== -1) {
      button.querySelector('use').setAttribute('href', '#' + config.icon);
      button.classList.add('has-icon');
    }
  });

  var visiblePorts = portIds.filter(function (id) { return !unused(id); });
  if (!visiblePorts.length) document.body.classList.add('no-ports');
  var buttons = Array.prototype.slice.call(document.querySelectorAll('button[data-app]')).filter(function (button) { return !unused(button.id); });
  var allowed = buttons.map(function (button) { return button.getAttribute('data-app'); });
  var navigation = {
    xbox: {right: visiblePorts[0], up: 'lg-home', down: 'apple-tv'},
    'lg-home': {down: 'xbox', right: 'game'},
    game: {down: 'xbox', left: 'lg-home', right: 'tv-settings'},
    'tv-settings': {down: visiblePorts[0] || 'xbox', left: 'game'},
    'apple-tv': {up: 'xbox', right: 'youtube'},
    youtube: {up: 'xbox', left: 'apple-tv', right: 'browser'},
    browser: {up: visiblePorts[visiblePorts.length - 1] || 'xbox', left: 'youtube'}
  };
  visiblePorts.forEach(function (id, index) {
    navigation[id] = {left: 'xbox', up: visiblePorts[index - 1] || 'tv-settings', down: visiblePorts[index + 1] || 'browser'};
  });

  function message(text) {
    notice.textContent = text;
    notice.hidden = false;
    window.clearTimeout(noticeTimer);
    noticeTimer = window.setTimeout(function () { notice.hidden = true; }, 6500);
  }

  function pad(value) {
    return value < 10 ? '0' + value : String(value);
  }

  function tick() {
    var now = new Date();
    window.clearTimeout(clockTimer);
    if (!clockTime) return;
    clockTime.textContent = pad(now.getHours()) + ':' + pad(now.getMinutes());
    clockDate.textContent = now.toLocaleDateString(undefined, {weekday: 'long', day: 'numeric', month: 'long'});
    clockTimer = window.setTimeout(tick, (60 - now.getSeconds()) * 1000);
  }

  function stopIdle() {
    window.clearTimeout(dimTimer);
    window.clearTimeout(sleepTimer);
  }

  function wake() {
    var wasSleeping = sleeping;
    sleeping = false;
    cover.hidden = true;
    document.body.classList.remove('is-idle');
    stopIdle();
    if (!alive || document.hidden) return wasSleeping;
    dimTimer = window.setTimeout(function () { document.body.classList.add('is-idle'); }, 45000);
    sleepTimer = window.setTimeout(function () { sleeping = true; cover.hidden = false; notice.hidden = true; }, 120000);
    return wasSleeping;
  }

  function focus(id) {
    var target = document.getElementById(id);
    if (target) target.focus();
  }

  // The activated control stays bright and says what it is doing while the TV switches.
  function showLaunching(appid) {
    var button = buttons[allowed.indexOf(appid)];
    var status = button.querySelector('[data-status]');
    launching = {button: button, status: status, text: status ? status.textContent : ''};
    button.classList.add('is-launching');
    if (status) status.textContent = button.getAttribute('data-busy');
  }

  function finishLaunch() {
    busy = false;
    document.body.classList.remove('is-busy');
    window.clearTimeout(launchTimer);
    bridge = null;
    if (!launching) return;
    launching.button.classList.remove('is-launching');
    if (launching.status) launching.status.textContent = launching.text;
    launching = null;
  }

  function launch(appid, label) {
    if (allowed.indexOf(appid) === -1 || busy) return;
    wake();
    if (preview) {
      busy = true;
      document.body.classList.add('is-busy');
      showLaunching(appid);
      launchTimer = window.setTimeout(finishLaunch, 1500);
      message('Preview: open ' + label + '.');
      return;
    }
    if (typeof window.PalmServiceBridge !== 'function') {
      message('TV controls are unavailable here. Open HDMI Home on the TV.');
      return;
    }
    busy = true;
    document.body.classList.add('is-busy');
    showLaunching(appid);
    var request = new window.PalmServiceBridge();
    bridge = request;
    launchTimer = window.setTimeout(function () {
      if (bridge !== request) return;
      if (typeof request.cancel === 'function') request.cancel();
      finishLaunch();
      message('No reply from the TV. Use the Input button, or try again.');
    }, 8000);
    request.onservicecallback = function (response) {
      if (bridge !== request) return;
      finishLaunch();
      try {
        var result = JSON.parse(response);
        if (result.returnValue !== true) message('Could not open ' + label + '. Use the TV remote or try again.');
      } catch (error) {
        message('The TV returned an unreadable reply. Use the Input button.');
      }
    };
    try {
      if (appid === 'com.webos.app.home') {
        request.call('luna://org.webosbrew.hbchannel.service/exec', JSON.stringify({command: stockHomeCommand}));
      } else {
        request.call('luna://com.webos.applicationManager/launch', JSON.stringify({id: appid, params: {}}));
      }
    } catch (error) {
      finishLaunch();
      message('Could not reach TV controls. Use the Input button.');
    }
  }

  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (wake()) return;
      launch(button.getAttribute('data-app'), button.getAttribute('data-label'));
    });
    button.addEventListener('mouseenter', function () { if (!sleeping) button.focus(); });
    button.addEventListener('focus', function () { if (!sleeping) wake(); });
  });

  document.addEventListener('keydown', function (event) {
    if (wake()) { event.preventDefault(); event.stopPropagation(); return; }
    var code = event.keyCode;
    var direction = {37: 'left', 38: 'up', 39: 'right', 40: 'down'}[code];
    if (direction) {
      event.preventDefault();
      var current = document.activeElement.id;
      if (!navigation[current]) focus('xbox');
      else if (navigation[current][direction]) focus(navigation[current][direction]);
    } else if (code === 461 || code === 27) {
      event.preventDefault();
      launch('com.webos.app.hdmi2', 'Xbox Series X');
    } else if (code === 405) {
      event.preventDefault(); launch('com.webos.app.gameoptimizer', 'Game Optimizer');
    } else if (code === 406) {
      event.preventDefault(); launch('com.palm.app.settings', 'TV Settings');
    }
  });

  document.addEventListener('pointermove', function () { if (!sleeping) wake(); }, {passive: true});
  cover.addEventListener('click', function (event) { event.preventDefault(); event.stopPropagation(); wake(); });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { stopIdle(); finishLaunch(); window.clearTimeout(clockTimer); }
    else { tick(); wake(); focus('xbox'); }
  });
  window.addEventListener('webOSLaunch', function () { wake(); focus('xbox'); });
  window.addEventListener('unload', function () { alive = false; stopIdle(); finishLaunch(); window.clearTimeout(noticeTimer); window.clearTimeout(clockTimer); });
  if (preview) document.getElementById('preview-banner').hidden = false;
  tick();
  wake();
  focus('xbox');
}());
