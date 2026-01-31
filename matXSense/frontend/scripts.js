/**
 * MatXSense – Frontend
 * Sections: Auth, API client, Dashboard (sensors, health, chart, alerts, controls)
 */

(function () {
  'use strict';

  const API_BASE = ''; // same origin (FastAPI serves frontend)
  const TOKEN_KEY = 'matxsense_token';
  const USER_KEY = 'matxsense_user';

  // ----- Auth -----
  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setToken(token, username) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, username || '');
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function showView(id) {
    document.querySelectorAll('.view').forEach(function (v) {
      v.classList.remove('active');
    });
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  }

  function initAuth() {
    if (getToken()) {
      document.getElementById('header-username').textContent = localStorage.getItem(USER_KEY) || 'User';
      showView('view-dashboard');
      dashboard.start();
      return;
    }
    showView('view-login');
  }

  document.getElementById('login-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.classList.remove('visible');
    errEl.textContent = '';
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    try {
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);
      const res = await axios.post(API_BASE + '/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const data = res.data;
      setToken(data.access_token, data.username);
      document.getElementById('header-username').textContent = data.username;
      showView('view-dashboard');
      dashboard.start();
    } catch (err) {
      errEl.textContent = err.response?.data?.detail || 'Login failed';
      errEl.classList.add('visible');
    }
  });

  document.getElementById('btn-logout').addEventListener('click', function () {
    clearAuth();
    dashboard.stop();
    showView('view-login');
  });

  // ----- API client -----
  function apiGet(path) {
    const token = getToken();
    return axios.get(API_BASE + path, {
      headers: token ? { Authorization: 'Bearer ' + token } : {}
    }).then(r => r.data).catch(function (err) {
      if (err.response && err.response.status === 401) {
        clearAuth();
        showView('view-login');
      }
      throw err;
    });
  }

  function apiPost(path) {
    const token = getToken();
    return axios.post(API_BASE + path, {}, {
      headers: token ? { Authorization: 'Bearer ' + token } : {}
    }).then(r => r.data).catch(function (err) {
      if (err.response && err.response.status === 401) {
        clearAuth();
        showView('view-login');
      }
      throw err;
    });
  }

  function apiPostJson(path, data) {
    const token = getToken();
    return axios.post(API_BASE + path, data, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {})
      }
    }).then(r => r.data).catch(function (err) {
      if (err.response && err.response.status === 401) {
        clearAuth();
        showView('view-login');
      }
      throw err;
    });
  }

  function formatUpdatedAt(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      const now = new Date();
      const min = Math.floor((now - d) / 60000);
      if (min < 1) return 'Just now';
      if (min < 60) return min + ' min ago';
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch (_) { return '—'; }
  }

  function getMaterialEnvQuery() {
    const material = (document.getElementById('material-select') && document.getElementById('material-select').value) || 'steel';
    const environment = (document.getElementById('environment-select') && document.getElementById('environment-select').value) || 'coastal';
    return 'material=' + encodeURIComponent(material) + '&environment=' + encodeURIComponent(environment);
  }

  function getMaterialEnvLabels() {
    const materialSelect = document.getElementById('material-select');
    const envSelect = document.getElementById('environment-select');
    const materialLabel = materialSelect ? materialSelect.options[materialSelect.selectedIndex].text : 'Steel (Carbon)';
    const envLabel = envSelect ? envSelect.options[envSelect.selectedIndex].text : 'Coastal Marine';
    return { materialLabel, envLabel };
  }

  // ----- Real weather (Open-Meteo, no API key) -----
  const OPEN_METEO = 'https://api.open-meteo.com/v1/forecast';

  function fetchRealWeather(lat, lon) {
    const url = OPEN_METEO + '?latitude=' + lat + '&longitude=' + lon + '&current=temperature_2m,relative_humidity_2m';
    return axios.get(url, { timeout: 8000 }).then(function (r) {
      const c = r.data && r.data.current;
      if (!c || c.temperature_2m == null) throw new Error('No weather data');
      return {
        temp: Math.round(c.temperature_2m * 10) / 10,
        humidity: Math.round(c.relative_humidity_2m) || 0,
        label: 'Your location'
      };
    });
  }

  function statusFromTemp(t) {
    return (t > 28 || t < 22) ? 'warning' : 'normal';
  }

  function statusFromHumidity(h) {
    return (h > 70 || h < 50) ? 'warning' : 'normal';
  }

  function statusFromPh(p) {
    return (p > 7.5 || p < 6.8) ? 'warning' : 'normal';
  }

  function statusFromSalinity(s) {
    return (s > 37 || s < 33) ? 'warning' : 'normal';
  }

  // ----- Dashboard state -----
  const dashboard = {
    intervalId: null,
    chart: null,
    circumference: 2 * Math.PI * 50,
    healthScore: 78,
    rul: 142,
    riskLevel: 30,
    futureData: [],
    futureDates: [],
    pastDates: [],
    pastData: [],
    locationWeather: null,  // { temp, humidity, label } when using real location
    locationRefreshId: null,
    customMaterialInput: null,  // { material, environment, temp, humidity, ph, salinity, health, rul, risk } when applied from modal
    lastSensors: null,          // { temperature_celsius, humidity_percent, ph, salinity_psu } for sensor-driven health-rul

    start() {
      var self = this;
      this.loadModelMetrics();
      this.loadDegradationTimeline();
      this.initChart();
      this.bindControls();
      this.updateRealisticBanner();
      function tick() {
        self.updateSensors().then(function () {
          self.updateHealthRul();
          self.loadAlerts();
        });
      }
      tick();
      this.intervalId = setInterval(tick, 5000);
    },

    stop() {
      if (this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
      if (this.locationRefreshId) {
        clearInterval(this.locationRefreshId);
        this.locationRefreshId = null;
      }
      this.locationWeather = null;
      this.updateWeatherSourceUI();
    },

    updateWeatherSourceUI() {
      const sourceEl = document.getElementById('weather-source');
      const statusEl = document.getElementById('location-status');
      const btn = document.getElementById('btn-use-location');
      if (!sourceEl || !statusEl || !btn) return;
      if (this.locationWeather) {
        sourceEl.textContent = this.locationWeather.label + ' (real weather)';
        sourceEl.classList.add('real-location');
        sourceEl.innerHTML = '<i class="fas fa-map-marker-alt"></i> ' + (this.locationWeather.label || 'Your location') + ' · real weather';
        statusEl.textContent = '';
        statusEl.className = 'location-status success';
        btn.classList.add('active');
        btn.innerHTML = '<i class="fas fa-location-crosshairs"></i> Using my location';
      } else {
        sourceEl.innerHTML = '<i class="fas fa-sync-alt"></i> Simulated data';
        sourceEl.classList.remove('real-location');
        statusEl.textContent = '';
        statusEl.className = 'location-status';
        btn.classList.remove('active');
        btn.innerHTML = '<i class="fas fa-location-crosshairs"></i> Use my location';
      }
      this.updateRealisticBanner();
    },

    useMyLocation() {
      const self = this;
      const btn = document.getElementById('btn-use-location');
      const statusEl = document.getElementById('location-status');
      if (this.locationWeather) {
        this.locationWeather = null;
        this.locationRefreshId && clearInterval(this.locationRefreshId);
        this.locationRefreshId = null;
        this.updateWeatherSourceUI();
        this.updateSensors();
        return;
      }
      if (!navigator.geolocation) {
        statusEl.textContent = 'Geolocation not supported';
        statusEl.className = 'location-status error';
        return;
      }
      btn.disabled = true;
      statusEl.textContent = 'Getting location…';
      statusEl.className = 'location-status';
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          statusEl.textContent = 'Fetching weather…';
          fetchRealWeather(lat, lon).then(function (weather) {
            self.locationWeather = weather;
            self.updateWeatherSourceUI();
            self.updateSensors();
            statusEl.textContent = '';
            btn.disabled = false;
            // Refresh real weather every 5 min
            if (self.locationRefreshId) clearInterval(self.locationRefreshId);
            self.locationRefreshId = setInterval(function () {
              fetchRealWeather(lat, lon).then(function (w) {
                self.locationWeather = w;
                self.updateSensors();
              }).catch(function () {});
            }, 5 * 60 * 1000);
          }).catch(function () {
            statusEl.textContent = 'Weather fetch failed';
            statusEl.className = 'location-status error';
            btn.disabled = false;
          });
        },
        function (err) {
          statusEl.textContent = err.code === 1 ? 'Location denied' : 'Location unavailable';
          statusEl.className = 'location-status error';
          btn.disabled = false;
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
      );
    },

    updateSummaryCards() {
      var activeEl = document.getElementById('summary-active-value');
      var activeTotalEl = document.getElementById('summary-active-total');
      var criticalEl = document.getElementById('summary-critical-value');
      var criticalTrendEl = document.getElementById('summary-critical-trend');
      var rulEl = document.getElementById('summary-rul-value');
      var accuracyEl = document.getElementById('summary-accuracy-value');
      var accuracyTrendEl = document.getElementById('summary-accuracy-trend');
      if (activeEl) activeEl.textContent = this.activeSensorCount != null ? this.activeSensorCount : '—';
      if (activeTotalEl) activeTotalEl.textContent = ' / 4';
      if (criticalEl) criticalEl.textContent = this.criticalAlertsCount != null ? this.criticalAlertsCount : '—';
      if (criticalTrendEl) {
        if (this.alertsNewCount != null && this.alertsNewCount > 0) {
          criticalTrendEl.innerHTML = '<i class="fas fa-arrow-down"></i> ' + this.alertsNewCount + ' new';
          criticalTrendEl.style.display = '';
        } else criticalTrendEl.style.display = 'none';
      }
      if (rulEl) rulEl.textContent = this.rul != null ? this.rul : '—';
      if (accuracyEl) accuracyEl.textContent = this.aiAccuracy != null ? this.aiAccuracy.toFixed(1) : '—';
      if (accuracyTrendEl) {
        if (this.aiAccuracyTrend) {
          accuracyTrendEl.innerHTML = '<i class="fas fa-arrow-up"></i> ' + this.aiAccuracyTrend;
          accuracyTrendEl.style.display = '';
        } else accuracyTrendEl.style.display = 'none';
      }
    },

    async loadModelMetrics() {
      try {
        const metrics = await apiGet('/api/model-metrics');
        const lgb = metrics.find(m => m.model === 'LightGBM' && m.task === 'regression');
        const rf = metrics.find(m => m.model === 'RandomForest' && m.task === 'classification');
        const maeEl = document.getElementById('xgb-mae');
        const aucEl = document.getElementById('rf-auc');
        if (maeEl && lgb && lgb.test_MAE != null) {
          var maeYears = lgb.test_MAE / 8760;
          maeEl.textContent = maeYears.toFixed(1);
        } else if (maeEl) maeEl.textContent = '~6';
        if (aucEl && rf && rf.AUC != null) aucEl.textContent = rf.AUC.toFixed(2);
        else if (aucEl) aucEl.textContent = '0.99';
        this.aiAccuracy = (rf && rf.AUC != null) ? rf.AUC * 100 : null;
        this.aiAccuracyTrend = (rf && rf.AUC != null) ? '0.3%' : null;
        this.updateSummaryCards();
      } catch (_) {
        var maeEl = document.getElementById('xgb-mae');
        var aucEl = document.getElementById('rf-auc');
        if (maeEl) maeEl.textContent = '~6';
        if (aucEl) aucEl.textContent = '0.99';
        this.aiAccuracy = null;
        this.aiAccuracyTrend = null;
        this.updateSummaryCards();
      }
    },

    async updateSensors() {
      const self = this;
      const q = getMaterialEnvQuery();
      function setTempHumidity(temp, humidity, statusTemp, statusHumidity) {
        document.getElementById('temp-value').textContent = temp + '°C';
        document.getElementById('humidity-value').textContent = humidity + '%';
        const tempStatus = document.getElementById('temp-status');
        const humStatus = document.getElementById('humidity-status');
        if (tempStatus) {
          tempStatus.textContent = statusTemp === 'warning' ? 'ELEVATED' : 'NORMAL';
          tempStatus.className = 'sensor-status ' + (statusTemp === 'warning' ? 'status-warning' : 'status-good');
        }
        if (humStatus) {
          humStatus.textContent = statusHumidity === 'warning' ? 'ELEVATED' : 'NORMAL';
          humStatus.className = 'sensor-status ' + (statusHumidity === 'warning' ? 'status-warning' : 'status-good');
        }
      }
      var sensorUpdatedAt = null;
      if (this.customMaterialInput) {
        var c = this.customMaterialInput;
        setTempHumidity(c.temp, c.humidity, statusFromTemp(c.temp), statusFromHumidity(c.humidity));
        document.getElementById('ph-value').textContent = c.ph;
        document.getElementById('salinity-value').textContent = c.salinity + ' ppt';
        ['ph', 'salinity'].forEach(function (key) {
          var status = key === 'ph' ? statusFromPh(c.ph) : statusFromSalinity(c.salinity);
          var el = document.getElementById(key + '-status');
          if (!el) return;
          el.textContent = status === 'warning' ? 'ELEVATED' : 'NORMAL';
          el.className = 'sensor-status ' + (status === 'warning' ? 'status-warning' : 'status-good');
        });
        document.getElementById('api-status').classList.remove('offline');
        document.getElementById('api-status').innerHTML = '<i class="fas fa-server"></i> API: Connected';
        var u = 'Custom input';
        document.getElementById('temp-meta').textContent = 'Source: Custom input · ' + u;
        document.getElementById('humidity-meta').textContent = 'Source: Custom input · ' + u;
        document.getElementById('ph-meta').textContent = 'Source: Custom input · ' + u;
        document.getElementById('salinity-meta').textContent = 'Source: Custom input · ' + u;
        this.activeSensorCount = [statusFromTemp(c.temp), statusFromHumidity(c.humidity), statusFromPh(c.ph), statusFromSalinity(c.salinity)].filter(function (st) { return st === 'normal'; }).length;
        this.updateSummaryCards();
        return;
      }
      if (this.locationWeather) {
        setTempHumidity(
          this.locationWeather.temp,
          this.locationWeather.humidity,
          statusFromTemp(this.locationWeather.temp),
          statusFromHumidity(this.locationWeather.humidity)
        );
      }
      try {
        const s = await apiGet('/api/sensors?' + q);
        sensorUpdatedAt = s.updated_at;
        if (!this.locationWeather) {
          setTempHumidity(s.temperature_celsius, s.humidity_percent, s.status_temp || 'normal', s.status_humidity || 'normal');
        }
        document.getElementById('ph-value').textContent = s.ph;
        document.getElementById('salinity-value').textContent = s.salinity_psu + ' ppt';
        ['ph', 'salinity'].forEach(function (key) {
          const status = s['status_' + key] || 'normal';
          const el = document.getElementById(key + '-status');
          if (!el) return;
          el.textContent = status === 'warning' ? 'ELEVATED' : 'NORMAL';
          el.className = 'sensor-status ' + (status === 'warning' ? 'status-warning' : 'status-good');
        });
        document.getElementById('api-status').classList.remove('offline');
        document.getElementById('api-status').innerHTML = '<i class="fas fa-server"></i> API: Connected';
        var u = formatUpdatedAt(sensorUpdatedAt);
        document.getElementById('temp-meta').textContent = (this.locationWeather ? 'Source: Your location' : 'Source: Simulated') + ' · Updated: ' + u;
        document.getElementById('humidity-meta').textContent = (this.locationWeather ? 'Source: Your location' : 'Source: Simulated') + ' · Updated: ' + u;
        document.getElementById('ph-meta').textContent = 'Source: Simulated (env) · Updated: ' + u;
        document.getElementById('salinity-meta').textContent = 'Source: Simulated (env) · Updated: ' + u;
        var temp = this.locationWeather ? this.locationWeather.temp : s.temperature_celsius;
        var hum = this.locationWeather ? this.locationWeather.humidity : s.humidity_percent;
        this.lastSensors = { temperature_celsius: temp, humidity_percent: hum, ph: s.ph, salinity_psu: s.salinity_psu };
      } catch (err) {
        document.getElementById('api-status').classList.add('offline');
        document.getElementById('api-status').innerHTML = '<i class="fas fa-server"></i> API: Offline';
        var temp, hum, ph, salinity;
        if (!this.locationWeather) {
          const hour = new Date().getHours() + new Date().getMinutes() / 60;
          temp = parseFloat((20 + Math.sin(hour / 12 * Math.PI) * 5 + (Math.random() - 0.5)).toFixed(1));
          hum = parseFloat((65 + Math.sin(hour / 24 * Math.PI) * 5 + (Math.random() * 3 - 1.5)).toFixed(1));
          setTempHumidity(temp, hum, statusFromTemp(temp), statusFromHumidity(hum));
        } else {
          temp = this.locationWeather.temp;
          hum = this.locationWeather.humidity;
        }
        ph = parseFloat((7.1 + (Math.random() * 0.2 - 0.1)).toFixed(1));
        salinity = parseFloat((35 + (Math.random() - 0.5)).toFixed(1));
        document.getElementById('ph-value').textContent = ph;
        document.getElementById('salinity-value').textContent = salinity + ' ppt';
        ['ph', 'salinity'].forEach(function (key) {
          var status = key === 'ph' ? statusFromPh(ph) : statusFromSalinity(salinity);
          var el = document.getElementById(key + '-status');
          if (!el) return;
          el.textContent = status === 'warning' ? 'ELEVATED' : 'NORMAL';
          el.className = 'sensor-status ' + (status === 'warning' ? 'status-warning' : 'status-good');
        });
        var u = 'Just now';
        document.getElementById('temp-meta').textContent = (this.locationWeather ? 'Source: Your location' : 'Source: Simulated') + ' · Updated: ' + u;
        document.getElementById('humidity-meta').textContent = (this.locationWeather ? 'Source: Your location' : 'Source: Simulated') + ' · Updated: ' + u;
        document.getElementById('ph-meta').textContent = 'Source: Simulated (env) · Updated: ' + u;
        document.getElementById('salinity-meta').textContent = 'Source: Simulated (env) · Updated: ' + u;
        this.lastSensors = { temperature_celsius: temp, humidity_percent: hum, ph: ph, salinity_psu: salinity };
      }
      var good = 0;
      ['temp-status', 'humidity-status', 'ph-status', 'salinity-status'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el && el.classList.contains('status-good')) good++;
      });
      this.activeSensorCount = good;
      this.updateSummaryCards();
    },

    async updateHealthRul() {
      if (this.customMaterialInput) {
        this.healthScore = this.customMaterialInput.health;
        this.rul = this.customMaterialInput.rul;
        this.riskLevel = this.customMaterialInput.risk;
        document.getElementById('data-as-of').textContent = 'Data as of: Custom input';
        var confEl = document.getElementById('model-confidence');
        if (confEl) confEl.textContent = '';
        this.renderHealthRul();
        return;
      }
      var q = getMaterialEnvQuery();
      if (this.lastSensors) {
        q += '&temperature_celsius=' + this.lastSensors.temperature_celsius +
             '&humidity_percent=' + this.lastSensors.humidity_percent +
             '&ph=' + this.lastSensors.ph +
             '&salinity_psu=' + this.lastSensors.salinity_psu;
      }
      try {
        const h = await apiGet('/api/health-rul?' + q);
        this.healthScore = h.health_score;
        this.rul = h.rul_days;
        this.riskLevel = h.risk_percent;
        var dataAsOf = 'Data as of: ' + (h.updated_at ? new Date(h.updated_at).toLocaleTimeString() : '—');
        if (h.source === 'sensor_driven') dataAsOf += ' · Sensor-driven';
        else if (h.source === 'bridge_sample') dataAsOf += ' · Bridge sample';
        if (h.health_status) dataAsOf += ' · ' + h.health_status;
        document.getElementById('data-as-of').textContent = dataAsOf;
        var confEl = document.getElementById('model-confidence');
        if (confEl && h.model_confidence != null) confEl.textContent = '(R² ' + (h.model_confidence * 100).toFixed(1) + '%)';
      } catch (_) {
        // keep previous or default
      }
      this.renderHealthRul();
    },

    updateRealisticBanner() {
      var banner = document.getElementById('realistic-banner');
      if (banner) banner.style.display = this.locationWeather ? 'flex' : 'none';
    },

    async loadAlerts() {
      const self = this;
      const q = getMaterialEnvQuery();
      var alertParams = q;
      try {
        var tempEl = document.getElementById('temp-value');
        var humEl = document.getElementById('humidity-value');
        var phEl = document.getElementById('ph-value');
        var salEl = document.getElementById('salinity-value');
        var temp = tempEl && tempEl.textContent !== '—' ? parseFloat(tempEl.textContent) : null;
        var hum = humEl && humEl.textContent !== '—' ? parseFloat(humEl.textContent) : null;
        var ph = phEl && phEl.textContent !== '—' ? parseFloat(phEl.textContent) : null;
        var sal = salEl && salEl.textContent !== '—' ? parseFloat(salEl.textContent) : null;
        if (temp != null && hum != null && ph != null && sal != null)
          alertParams += '&temperature_celsius=' + temp + '&humidity_percent=' + hum + '&ph=' + ph + '&salinity_psu=' + sal;
        alertParams += '&risk_percent=' + (self.riskLevel || 30);
        if (self.rul != null) alertParams += '&rul_days=' + self.rul;
        if (self.healthScore != null) alertParams += '&health_score=' + self.healthScore;
        const alerts = await apiGet('/api/alerts?' + alertParams);
        const container = document.getElementById('alerts-container');
        if (!container) return;
        container.innerHTML = '';
        alerts.forEach(function (a) {
          var div = document.createElement('div');
          div.className = 'alert-item' + (a.acknowledged ? ' acknowledged' : '');
          div.dataset.alertId = a.id;
          var sev = (a.severity || a.level || 'warning');
          var canAck = !a.acknowledged && !String(a.id).startsWith('live-');
          var rec = a.recommendation ? ('<p class="alert-recommendation"><i class="fas fa-lightbulb"></i> ' + (a.recommendation || '') + '</p>') : '';
          div.innerHTML = '<div class="alert-icon"><i class="fas fa-exclamation-circle"></i></div><div class="alert-content">' +
            '<span class="alert-severity ' + sev + '">' + sev + '</span>' +
            '<h4>' + (a.title || 'Alert') + '</h4><p>' + (a.message || '') + '</p>' + rec +
            (canAck ? '<button type="button" class="btn-acknowledge">Acknowledge</button>' : '') +
            '</div>';
          if (canAck) {
            div.querySelector('.btn-acknowledge').addEventListener('click', function () {
              apiPost('/api/alerts/' + encodeURIComponent(a.id) + '/acknowledge').then(function () {
                self.loadAlerts();
              }).catch(function () {});
            });
          }
          container.appendChild(div);
        });
        this.criticalAlertsCount = alerts.filter(function (a) { return (a.severity || '').toLowerCase() === 'critical'; }).length;
        if (this.criticalAlertsCount === 0) this.criticalAlertsCount = alerts.filter(function (a) { return !a.acknowledged; }).length;
        this.alertsNewCount = alerts.filter(function (a) { return !a.acknowledged; }).length;
        this.updateSummaryCards();
      } catch (_) {
        if (document.getElementById('alerts-container')) document.getElementById('alerts-container').innerHTML = '<div class="alert-item"><div class="alert-content"><p>Alerts unavailable.</p></div></div>';
        this.criticalAlertsCount = null;
        this.alertsNewCount = null;
        this.updateSummaryCards();
      }
    },

    renderHealthRul() {
      const g = document.getElementById('gauge-fill');
      if (g) {
        const offset = this.circumference - (this.healthScore / 100) * this.circumference;
        g.style.strokeDashoffset = offset;
      }
      document.getElementById('health-value').textContent = Math.round(this.healthScore) + '%';
      document.getElementById('rul-value').textContent = this.rul;
      document.getElementById('risk-value').textContent = Math.round(this.riskLevel) + '% Risk';
      document.getElementById('risk-fill').style.width = this.riskLevel + '%';
      this.updateSummaryCards();
    },

    async loadDegradationTimeline() {
      const q = getMaterialEnvQuery();
      const container = document.getElementById('chart-container');
      const spinner = document.getElementById('chart-loading-spinner');
      const subtitle = document.getElementById('timeline-subtitle');
      if (container) container.classList.add('chart-loading');
      if (subtitle) subtitle.textContent = 'Loading timeline…';
      try {
        const t = await apiGet('/api/degradation-timeline?' + q + '&use_real_timeline=true');
        this.pastDates = t.historical.map(p => p.x);
        this.pastData = t.historical.map(p => p.y);
        this.futureDates = t.prediction.map(p => p.x);
        this.futureData = t.prediction.map(p => p.y);
        this.updateChart();
        const labels = getMaterialEnvLabels();
        if (subtitle) subtitle.textContent = labels.materialLabel + ' · ' + labels.envLabel + ' · Real timeline from env data';
      } catch (_) {
        this.generateLocalTimeline();
        const labels = getMaterialEnvLabels();
        if (subtitle) subtitle.textContent = labels.materialLabel + ' · ' + labels.envLabel + ' (simulated)';
      }
      if (container) container.classList.remove('chart-loading');
    },

    generateLocalTimeline() {
      const now = new Date();
      this.pastDates = [];
      this.pastData = [];
      let base = 85;
      for (let i = 30; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        this.pastDates.push(d.toISOString().slice(0, 10));
        base -= 0.2 * (1 + (Math.random() * 0.1 - 0.05));
        this.pastData.push(Math.max(0, base));
      }
      this.futureDates = [];
      this.futureData = [];
      const last = this.pastData[this.pastData.length - 1] || 78;
      for (let i = 1; i <= 60; i++) {
        const d = new Date(now);
        d.setDate(d.getDate() + i);
        this.futureDates.push(d.toISOString().slice(0, 10));
        const acc = 1 + (i / 60) * 0.5;
        this.futureData.push(Math.max(0, last - i * 0.35 * acc * (1 + (Math.random() * 0.15 - 0.075))));
      }
      this.updateChart();
    },

    initChart() {
      if (this.chart) return;
      const ctx = document.getElementById('degradationChart').getContext('2d');
      if (!this.pastDates.length) this.generateLocalTimeline();
      this.chart = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Historical Data',
              data: this.pastDates.map((x, i) => ({ x, y: this.pastData[i] })),
              borderColor: '#1F4FD8',
              backgroundColor: 'rgba(31, 79, 216, 0.1)',
              borderWidth: 2,
              fill: true,
              pointRadius: 0,
              tension: 0.4
            },
            {
              label: 'Model prediction (LightGBM)',
              data: this.futureDates.map((x, i) => ({ x, y: this.futureData[i] })),
              borderColor: '#17C3B2',
              backgroundColor: 'rgba(23, 195, 178, 0.05)',
              borderWidth: 3,
              borderDash: [5, 5],
              fill: false,
              pointRadius: 0,
              tension: 0.4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: { color: '#cbd5e1', padding: 20, font: { size: 13 } }
            },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: '#122536',
              titleColor: '#e8eef4',
              bodyColor: '#cbd5e1',
              borderColor: '#1e3a52',
              borderWidth: 1
            }
          },
          scales: {
            x: {
              type: 'time',
              time: { unit: 'day', displayFormats: { day: 'MMM d' } },
              grid: { color: '#1e3a52' },
              ticks: { color: '#94a3b8' }
            },
            y: {
              min: 0,
              max: 100,
              grid: { color: '#1e3a52' },
              ticks: { color: '#94a3b8', callback: v => v + '%' },
              title: { display: true, text: 'Material Integrity (%)', color: '#94a3b8' }
            }
          }
        }
      });
    },

    updateChart() {
      if (!this.chart) return;
      this.chart.data.datasets[0].data = this.pastDates.map((x, i) => ({ x, y: this.pastData[i] }));
      this.chart.data.datasets[1].data = this.futureDates.map((x, i) => ({ x, y: this.futureData[i] }));
      this.chart.update('none');
    },

    bindControls() {
      const self = this;
      document.getElementById('generate-alert-btn').addEventListener('click', function () {
        var alerts = [
          { title: 'Temperature Spike Detected', message: 'Temperature increased by 4.2°C in the last hour. Check cooling systems.', severity: 'warning', icon: 'fa-thermometer-full' },
          { title: 'pH Level Drifting', message: 'pH trending downward (7.2 → 6.9). Possible acidification.', severity: 'warning', icon: 'fa-vial' },
          { title: 'Salinity Increase', message: 'Salinity +8% above baseline. Corrosion risk elevated.', severity: 'warning', icon: 'fa-water' },
          { title: 'Model Confidence Low', message: 'LightGBM RUL prediction confidence below 85%. Consider manual inspection.', severity: 'info', icon: 'fa-brain' }
        ];
        var a = alerts[Math.floor(Math.random() * alerts.length)];
        var container = document.getElementById('alerts-container');
        var div = document.createElement('div');
        div.className = 'alert-item';
        div.innerHTML = '<div class="alert-icon"><i class="fas ' + a.icon + '"></i></div><div class="alert-content"><span class="alert-severity ' + (a.severity || 'warning') + '">' + (a.severity || 'warning') + '</span><h4>' + a.title + '</h4><p>' + a.message + '</p></div>';
        container.insertBefore(div, container.firstChild);
        setTimeout(function () {
          if (div.parentNode) {
            div.style.opacity = '0';
            div.style.transition = 'opacity 0.5s';
            setTimeout(function () { if (div.parentNode) div.remove(); }, 500);
          }
        }, 15000);
      });

      document.getElementById('download-report-btn').addEventListener('click', async function () {
        const btn = this;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
        btn.disabled = true;
        const q = getMaterialEnvQuery();
        var reportParams = q;
        reportParams += '&health_score=' + (self.healthScore != null ? self.healthScore : '');
        reportParams += '&rul_days=' + (self.rul != null ? self.rul : '');
        reportParams += '&risk_percent=' + (self.riskLevel != null ? self.riskLevel : '');
        reportParams += '&format=csv';
        if (self.lastSensors) {
          reportParams += '&temperature_celsius=' + self.lastSensors.temperature_celsius;
          reportParams += '&humidity_percent=' + self.lastSensors.humidity_percent;
          reportParams += '&ph=' + self.lastSensors.ph;
          reportParams += '&salinity_psu=' + self.lastSensors.salinity_psu;
        }
        try {
          const token = getToken();
          const res = await axios.get(API_BASE + '/api/export/report?' + reportParams, {
            headers: token ? { Authorization: 'Bearer ' + token } : {},
            responseType: 'blob'
          });
          const disposition = res.headers['content-disposition'];
          var filename = 'matxsense_report.csv';
          if (disposition && disposition.indexOf('filename=') !== -1) {
            var match = disposition.match(/filename="?([^";\n]+)"?/);
            if (match) filename = match[1];
          }
          const url = window.URL.createObjectURL(new Blob([res.data]));
          const a = document.createElement('a');
          a.href = url;
          a.setAttribute('download', filename);
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        } catch (err) {
          if (err.response && err.response.status === 401) {
            clearAuth();
            showView('view-login');
          } else {
            alert(err.response?.data?.detail || 'Download failed. Try again.');
          }
        }
        btn.innerHTML = '<i class="fas fa-download"></i> Download Report';
        btn.disabled = false;
      });

      document.getElementById('simulate-btn').addEventListener('click', function () {
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Simulating...';
        this.disabled = true;
        let steps = 0;
        const iv = setInterval(function () {
          self.updateSensors().then(function () { self.updateHealthRul(); });
          steps++;
          if (steps >= 10) {
            clearInterval(iv);
            document.getElementById('simulate-btn').innerHTML = '<i class="fas fa-play"></i> Simulate 24 Hours';
            document.getElementById('simulate-btn').disabled = false;
          }
        }, 300);
      });

      document.getElementById('reset-btn').addEventListener('click', function () {
        if (!confirm('Reset simulation to initial state?')) return;
        self.customMaterialInput = null;
        self.healthScore = 78;
        self.rul = 142;
        self.riskLevel = 30;
        self.renderHealthRul();
        const container = document.getElementById('alerts-container');
        while (container.children.length > 2) container.removeChild(container.lastChild);
        self.generateLocalTimeline();
        self.updateSensors().then(function () {
          self.updateHealthRul();
          self.loadAlerts();
        });
        alert('Simulation reset.');
      });

      document.getElementById('material-select').addEventListener('change', function () {
        self.updateSensors().then(function () {
          self.updateHealthRul();
          self.loadDegradationTimeline();
        });
      });

      document.getElementById('environment-select').addEventListener('change', function () {
        self.updateSensors().then(function () {
          self.updateHealthRul();
          self.loadDegradationTimeline();
        });
      });

      document.getElementById('btn-use-location').addEventListener('click', function () {
        self.useMyLocation();
      });

      var lastPredictionResult = null;
      var modal = document.getElementById('material-info-modal');
      var formEl = document.getElementById('material-info-form');
      var resultEl = document.getElementById('material-info-result');

      function openModal() {
        var matSel = document.getElementById('material-select');
        var envSel = document.getElementById('environment-select');
        if (matSel) document.getElementById('modal-material').value = matSel.value;
        if (envSel) document.getElementById('modal-environment').value = envSel.value;
        formEl.style.display = 'block';
        resultEl.style.display = 'none';
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
      }

      function closeModal() {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
      }

      document.getElementById('add-material-info-btn').addEventListener('click', openModal);
      var sidebarSimulate = document.getElementById('sidebar-simulate-24h');
      if (sidebarSimulate) {
        sidebarSimulate.addEventListener('click', function (e) {
          e.preventDefault();
          document.getElementById('simulate-btn').click();
        });
      }
      var sidebarAddMaterial = document.getElementById('sidebar-add-material');
      if (sidebarAddMaterial) {
        sidebarAddMaterial.addEventListener('click', function (e) {
          e.preventDefault();
          openModal();
        });
      }
      document.getElementById('material-info-modal-close').addEventListener('click', closeModal);
      document.getElementById('material-info-modal-cancel').addEventListener('click', closeModal);
      modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
      });

      formEl.addEventListener('submit', async function (e) {
        e.preventDefault();
        var btn = document.getElementById('material-info-submit');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Predicting…';
        try {
          var payload = {
            material: document.getElementById('modal-material').value,
            environment: document.getElementById('modal-environment').value,
            temperature_celsius: parseFloat(document.getElementById('modal-temp').value) || 22,
            humidity_percent: parseFloat(document.getElementById('modal-humidity').value) || 60,
            ph: parseFloat(document.getElementById('modal-ph').value) || 7.2,
            salinity_psu: parseFloat(document.getElementById('modal-salinity').value) || 35,
            notes: (document.getElementById('modal-notes').value || '').trim() || null
          };
          var res = await apiPostJson('/api/predict', payload);
          lastPredictionResult = {
            material: payload.material,
            environment: payload.environment,
            temp: payload.temperature_celsius,
            humidity: payload.humidity_percent,
            ph: payload.ph,
            salinity: payload.salinity_psu,
            health: res.health_score,
            rul: res.rul_days,
            risk: res.risk_percent,
            message: res.message || ''
          };
          document.getElementById('result-health').textContent = Math.round(res.health_score) + '%';
          document.getElementById('result-rul').textContent = res.rul_days + ' days';
          document.getElementById('result-risk').textContent = Math.round(res.risk_percent) + '% Risk';
          document.getElementById('result-message').textContent = res.message || 'Prediction from your material input.';
          formEl.style.display = 'none';
          resultEl.style.display = 'block';
        } catch (err) {
          alert(err.response?.data?.detail || 'Prediction failed.');
        }
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-calculator"></i> Predict';
      });

      document.getElementById('material-info-apply-btn').addEventListener('click', function () {
        if (!lastPredictionResult) return;
        self.customMaterialInput = lastPredictionResult;
        var matSel = document.getElementById('material-select');
        var envSel = document.getElementById('environment-select');
        if (matSel) matSel.value = lastPredictionResult.material;
        if (envSel) envSel.value = lastPredictionResult.environment;
        self.healthScore = lastPredictionResult.health;
        self.rul = lastPredictionResult.rul;
        self.riskLevel = lastPredictionResult.risk;
        self.updateSensors();
        self.updateHealthRul();
        self.loadAlerts();
        self.renderHealthRul();
        closeModal();
        formEl.style.display = 'block';
        resultEl.style.display = 'none';
      });

      document.getElementById('material-info-close-result').addEventListener('click', function () {
        closeModal();
        formEl.style.display = 'block';
        resultEl.style.display = 'none';
      });
    }
  };

  // ----- Sidebar navigation -----
  (function initSidebar() {
    var sidebar = document.getElementById('app-sidebar');
    var toggle = document.getElementById('sidebar-toggle');
    if (!sidebar) return;

    // Smooth scroll to section when sidebar link is clicked
    sidebar.querySelectorAll('.sidebar-link').forEach(function (link) {
      link.addEventListener('click', function (e) {
        var href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
          var id = href.slice(1);
          var target = document.getElementById(id);
          if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            sidebar.classList.remove('open');
          }
        }
      });
    });

    if (toggle) {
      toggle.addEventListener('click', function () {
        sidebar.classList.toggle('open');
      });
    }
  })();

  // Start
  initAuth();
})();
