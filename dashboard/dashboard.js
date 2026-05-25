/**
 * Grandmaster.AI — Analytics Dashboard JavaScript
 *
 * Simulated data and Chart.js visualizations for:
 * - A/B Test Results (session length)
 * - Feature Adoption Funnel
 * - Engagement Over Time
 * - Retention Curves
 * - Revenue Impact
 */

// ── Chart.js Global Configuration ────────────────────────────────────
Chart.defaults.color = '#a0a0b8';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.06)';
Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 16;

// ── Animated Counter ─────────────────────────────────────────────────
function animateCounter(elementId, target, duration = 1500, prefix = '', suffix = '') {
  const el = document.getElementById(elementId);
  if (!el) return;

  const start = 0;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + (target - start) * eased;

    if (Number.isInteger(target)) {
      el.textContent = prefix + Math.round(current).toLocaleString() + suffix;
    } else {
      el.textContent = prefix + current.toFixed(1) + suffix;
    }

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  requestAnimationFrame(update);
}

// ── Chart 1: Session Length A/B Test ─────────────────────────────────
function renderSessionLengthChart() {
  const ctx = document.getElementById('sessionLengthChart');
  if (!ctx) return;

  // Simulated daily data over 14 days
  const days = Array.from({length: 14}, (_, i) => `Day ${i + 1}`);
  const controlData = [12.1, 11.8, 12.4, 12.0, 11.9, 12.3, 12.1, 11.7, 12.2, 12.0, 12.5, 11.9, 12.1, 12.2];
  const treatmentData = [12.3, 12.9, 13.2, 13.5, 13.8, 14.0, 13.7, 14.2, 14.1, 14.4, 14.3, 14.6, 14.5, 14.8];

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: days,
      datasets: [
        {
          label: 'Control (Standard)',
          data: controlData,
          borderColor: '#6a6a80',
          backgroundColor: 'rgba(106, 106, 128, 0.1)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: 'Treatment (+ Grandmaster.AI)',
          data: treatmentData,
          borderColor: '#a855f7',
          backgroundColor: 'rgba(168, 85, 247, 0.1)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} min`
          }
        }
      },
      scales: {
        y: {
          title: { display: true, text: 'Avg Session Length (min)' },
          min: 10,
          max: 16,
          grid: { color: 'rgba(255,255,255,0.04)' }
        },
        x: {
          grid: { display: false }
        }
      }
    }
  });
}

// ── Chart 2: Feature Adoption Funnel ─────────────────────────────────
function renderFunnelChart() {
  const ctx = document.getElementById('funnelChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [
        'Games Completed',
        'View Analysis',
        'Click Explain',
        'Read Full',
        'Rate (👍/👎)',
        'Use Again'
      ],
      datasets: [{
        data: [100000, 72000, 35200, 21100, 14000, 8400],
        backgroundColor: [
          'rgba(168, 85, 247, 0.7)',
          'rgba(168, 85, 247, 0.6)',
          'rgba(168, 85, 247, 0.5)',
          'rgba(168, 85, 247, 0.4)',
          'rgba(168, 85, 247, 0.3)',
          'rgba(168, 85, 247, 0.2)',
        ],
        borderColor: [
          'rgba(168, 85, 247, 0.9)',
          'rgba(168, 85, 247, 0.8)',
          'rgba(168, 85, 247, 0.7)',
          'rgba(168, 85, 247, 0.6)',
          'rgba(168, 85, 247, 0.5)',
          'rgba(168, 85, 247, 0.4)',
        ],
        borderWidth: 1,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.parsed.x.toLocaleString()} users`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            callback: (v) => v >= 1000 ? (v / 1000) + 'K' : v
          }
        },
        y: {
          grid: { display: false }
        }
      }
    }
  });
}

// ── Chart 3: Daily Engagement ────────────────────────────────────────
function renderEngagementChart() {
  const ctx = document.getElementById('engagementChart');
  if (!ctx) return;

  const days = Array.from({length: 30}, (_, i) => {
    const d = new Date(2025, 4, i + 1);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  });

  // Simulated daily usage with growth trend
  const dailyUsage = days.map((_, i) => {
    const base = 2000 + i * 120;
    const noise = Math.sin(i * 0.8) * 400 + Math.random() * 300;
    return Math.round(base + noise);
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: days,
      datasets: [{
        label: '"Explain My Blunder" Clicks',
        data: dailyUsage,
        backgroundColor: (ctx) => {
          const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 300);
          gradient.addColorStop(0, 'rgba(124, 58, 237, 0.6)');
          gradient.addColorStop(1, 'rgba(124, 58, 237, 0.1)');
          return gradient;
        },
        borderColor: 'rgba(168, 85, 247, 0.5)',
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true },
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
        }
      },
      scales: {
        y: {
          title: { display: true, text: 'Feature Usage' },
          grid: { color: 'rgba(255,255,255,0.04)' }
        },
        x: {
          grid: { display: false },
          ticks: { maxRotation: 45, maxTicksLimit: 10 }
        }
      }
    }
  });
}

// ── Chart 4: Retention Curves ────────────────────────────────────────
function renderRetentionChart() {
  const ctx = document.getElementById('retentionChart');
  if (!ctx) return;

  const retDays = ['D0', 'D1', 'D3', 'D7', 'D14', 'D30'];

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: retDays,
      datasets: [
        {
          label: 'With Grandmaster.AI',
          data: [100, 68, 52, 41, 33, 26],
          borderColor: '#a855f7',
          backgroundColor: 'rgba(168, 85, 247, 0.08)',
          borderWidth: 2.5,
          tension: 0.3,
          fill: true,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#a855f7',
        },
        {
          label: 'Without (Control)',
          data: [100, 58, 42, 30, 22, 16],
          borderColor: '#6a6a80',
          backgroundColor: 'rgba(106, 106, 128, 0.05)',
          borderWidth: 2,
          borderDash: [6, 4],
          tension: 0.3,
          fill: true,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#6a6a80',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        y: {
          title: { display: true, text: 'Retention (%)' },
          min: 0,
          max: 110,
          grid: { color: 'rgba(255,255,255,0.04)' }
        },
        x: {
          title: { display: true, text: 'Days Since Signup' },
          grid: { display: false }
        }
      }
    }
  });
}

// ── Chart 5: Satisfaction Distribution ──────────────────────────────
function renderSatisfactionChart() {
  const ctx = document.getElementById('satisfactionChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Very Helpful', 'Helpful', 'Neutral', 'Not Helpful', 'Misleading'],
      datasets: [{
        data: [42, 31, 15, 8, 4],
        backgroundColor: [
          '#10b981',
          '#34d399',
          '#6a6a80',
          '#f59e0b',
          '#ef4444',
        ],
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, font: { size: 11 } }
        },
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.parsed}%`
          }
        }
      }
    }
  });
}

// ── Chart 6: Premium Conversion ─────────────────────────────────────
function renderConversionChart() {
  const ctx = document.getElementById('conversionChart');
  if (!ctx) return;

  const weeks = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: weeks,
      datasets: [
        {
          label: 'Premium Conversion (Treatment)',
          data: [2.1, 2.8, 3.4, 3.9, 4.2, 4.5, 4.7, 4.9],
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          borderWidth: 2.5,
          tension: 0.4,
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 7,
          pointBackgroundColor: '#10b981',
        },
        {
          label: 'Premium Conversion (Control)',
          data: [2.0, 2.1, 2.1, 2.2, 2.1, 2.2, 2.1, 2.2],
          borderColor: '#6a6a80',
          borderDash: [6, 4],
          borderWidth: 2,
          tension: 0.4,
          fill: false,
          pointRadius: 4,
          pointHoverRadius: 7,
          pointBackgroundColor: '#6a6a80',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          backgroundColor: '#1a1a2e',
          titleColor: '#f0f0f5',
          bodyColor: '#a0a0b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        y: {
          title: { display: true, text: 'Conversion Rate (%)' },
          min: 0,
          max: 6,
          grid: { color: 'rgba(255,255,255,0.04)' }
        },
        x: {
          title: { display: true, text: 'Weeks Since Launch' },
          grid: { display: false }
        }
      }
    }
  });
}

// ── Initialize Everything ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Animate KPI counters
  setTimeout(() => {
    animateCounter('kpi-session', 14.8, 1500, '', ' min');
    animateCounter('kpi-adoption', 35.2, 1500, '', '%');
    animateCounter('kpi-satisfaction', 4.2, 1500, '', '/5');
    animateCounter('kpi-retention', 62.5, 1500, '+', '%');
  }, 300);

  // Render charts
  renderSessionLengthChart();
  renderFunnelChart();
  renderEngagementChart();
  renderRetentionChart();
  renderSatisfactionChart();
  renderConversionChart();
});
