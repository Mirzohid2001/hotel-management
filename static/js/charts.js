/**
 * Rivoj PMS — Chart.js grafiklar (Dashboard, PnL)
 */
(function () {
  "use strict";

  var instances = [];

  var COLORS = {
    accent: "#e86a0c",
    accentSoft: "#ff9a2e",
    ink: "#1a1410",
    muted: "#8a7a6a",
    ready: "#2f8a5b",
    dirty: "#c47a12",
    cleaning: "#5a8a72",
    inspected: "#6a9ab8",
    ooo: "#8a4040",
    occupied: "#3d5a80",
    green: "#2f8a5b",
    red: "#b54a32",
    purple: "#6a508a",
  };

  var ROOM_STATUS_COLORS = {
    ready: COLORS.ready,
    dirty: COLORS.dirty,
    cleaning: COLORS.cleaning,
    inspected: COLORS.inspected,
    out_of_order: COLORS.ooo,
  };

  var DONUT_PALETTE = [
    COLORS.accent,
    COLORS.accentSoft,
    COLORS.ready,
    COLORS.purple,
    COLORS.occupied,
    COLORS.dirty,
    COLORS.inspected,
  ];

  function destroyCharts() {
    instances.forEach(function (chart) {
      try {
        chart.destroy();
      } catch (e) { /* ignore */ }
    });
    instances = [];
  }

  function track(chart) {
    instances.push(chart);
    return chart;
  }

  function fmtMoney(value, currency) {
    try {
      return new Intl.NumberFormat(undefined, {
        maximumFractionDigits: 0,
      }).format(value) + (currency ? " " + currency : "");
    } catch (e) {
      return String(value);
    }
  }

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: COLORS.ink,
            font: { family: "system-ui, sans-serif", size: 11 },
            boxWidth: 12,
            padding: 14,
          },
        },
        tooltip: {
          backgroundColor: "rgba(24, 18, 14, 0.92)",
          titleColor: "#fff",
          bodyColor: "rgba(255, 246, 236, 0.9)",
          padding: 10,
          cornerRadius: 10,
        },
      },
    };
  }

  function initDashboardCharts(data) {
    if (!window.Chart || !data) return;

    var currency = data.currency || "";

    var trendCanvas = document.getElementById("chart-revenue-trend");
    if (trendCanvas && data.revenueTrend) {
      var td = data.revenueTrend;
      track(new Chart(trendCanvas, {
        type: "line",
        data: {
          labels: td.labels,
          datasets: [
            {
              label: "Tushum",
              data: td.revenue,
              borderColor: COLORS.accent,
              backgroundColor: "rgba(232, 106, 12, 0.12)",
              fill: true,
              tension: 0.35,
              yAxisID: "y",
              pointRadius: 4,
              pointHoverRadius: 6,
              pointBackgroundColor: COLORS.accent,
            },
            {
              label: "Bandlik %",
              data: td.occupancy,
              borderColor: COLORS.occupied,
              backgroundColor: "transparent",
              borderDash: [4, 3],
              tension: 0.35,
              yAxisID: "y1",
              pointRadius: 3,
              pointHoverRadius: 5,
            },
          ],
        },
        options: Object.assign({}, baseOptions(), {
          interaction: { mode: "index", intersect: false },
          scales: {
            x: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: { color: COLORS.muted, font: { size: 10 } },
            },
            y: {
              position: "left",
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
            y1: {
              position: "right",
              min: 0,
              max: 100,
              grid: { drawOnChartArea: false },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return v + "%"; },
              },
            },
          },
          plugins: Object.assign({}, baseOptions().plugins, {
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  if (ctx.dataset.yAxisID === "y1") {
                    return ctx.dataset.label + ": " + ctx.parsed.y + "%";
                  }
                  return ctx.dataset.label + ": " + fmtMoney(ctx.parsed.y, currency);
                },
              },
            },
          }),
        }),
      }));
    }

    var roomCanvas = document.getElementById("chart-room-status");
    if (roomCanvas && data.roomStatus && data.roomStatus.values.length) {
      var rs = data.roomStatus;
      var sliceColors = rs.statuses.map(function (s, i) {
        return ROOM_STATUS_COLORS[s] || DONUT_PALETTE[i % DONUT_PALETTE.length];
      });
      track(new Chart(roomCanvas, {
        type: "doughnut",
        data: {
          labels: rs.labels,
          datasets: [{
            data: rs.values,
            backgroundColor: sliceColors,
            borderWidth: 2,
            borderColor: "#fff",
            hoverOffset: 6,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          cutout: "62%",
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { position: "bottom" },
          }),
        }),
      }));
    }
  }

  function initPnlCharts(data) {
    if (!window.Chart || !data) return;

    var currency = data.currency || "";

    function donut(canvasId, block, title) {
      var canvas = document.getElementById(canvasId);
      if (!canvas || !block || !block.values.length) return;
      track(new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: block.labels,
          datasets: [{
            data: block.values,
            backgroundColor: block.labels.map(function (_, i) {
              return DONUT_PALETTE[i % DONUT_PALETTE.length];
            }),
            borderWidth: 2,
            borderColor: "#fff",
            hoverOffset: 6,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          cutout: "58%",
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { position: "bottom" },
            title: title ? { display: true, text: title, color: COLORS.ink, font: { size: 13, weight: "600" } } : undefined,
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return ctx.label + ": " + fmtMoney(ctx.parsed, currency);
                },
              },
            },
          }),
        }),
      }));
    }

    donut("chart-pnl-revenue", data.revenueDonut);
    donut("chart-pnl-expense", data.expenseDonut);

    var barCanvas = document.getElementById("chart-pnl-summary");
    if (barCanvas && data.summaryBar) {
      var sb = data.summaryBar;
      var barColors = [COLORS.green, COLORS.red, COLORS.red, COLORS.accent];
      track(new Chart(barCanvas, {
        type: "bar",
        data: {
          labels: sb.labels,
          datasets: [{
            data: sb.values,
            backgroundColor: barColors.map(function (c, i) {
              return i === 3 ? c : c + "cc";
            }),
            borderRadius: 8,
            borderSkipped: false,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return fmtMoney(ctx.parsed.y, currency);
                },
              },
            },
          }),
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: COLORS.muted },
            },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }
  }

  function initFlashCharts(data) {
    if (!window.Chart || !data) return;

    var currency = data.currency || "";

    var payCanvas = document.getElementById("chart-flash-payments");
    if (payCanvas && data.paymentMethods && data.paymentMethods.labels.length) {
      var pm = data.paymentMethods;
      track(new Chart(payCanvas, {
        type: "bar",
        data: {
          labels: pm.labels,
          datasets: [
            {
              label: "Kirim",
              data: pm.in,
              backgroundColor: COLORS.green + "cc",
              borderRadius: 6,
            },
            {
              label: "Chiqim",
              data: pm.out,
              backgroundColor: COLORS.red + "cc",
              borderRadius: 6,
            },
          ],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return ctx.dataset.label + ": " + fmtMoney(ctx.parsed.y, currency);
                },
              },
            },
          }),
          scales: {
            x: { grid: { display: false }, ticks: { color: COLORS.muted } },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }

    var revCanvas = document.getElementById("chart-flash-revenue");
    if (revCanvas && data.revenueDay) {
      var rd = data.revenueDay;
      track(new Chart(revCanvas, {
        type: "bar",
        data: {
          labels: rd.labels,
          datasets: [{
            data: rd.values,
            backgroundColor: [COLORS.accent, COLORS.occupied, COLORS.red],
            borderRadius: 8,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return fmtMoney(ctx.parsed.y, currency); },
              },
            },
          }),
          scales: {
            x: { grid: { display: false }, ticks: { color: COLORS.muted } },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }

    var arCanvas = document.getElementById("chart-flash-guest-ar");
    if (arCanvas && data.guestAr && data.guestAr.values.length) {
      var ar = data.guestAr;
      track(new Chart(arCanvas, {
        type: "bar",
        data: {
          labels: ar.labels,
          datasets: [{
            data: ar.values,
            backgroundColor: COLORS.accentSoft + "cc",
            borderRadius: 6,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          indexAxis: "y",
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return fmtMoney(ctx.parsed.x, currency); },
              },
            },
          }),
          scales: {
            x: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
            y: { grid: { display: false }, ticks: { color: COLORS.muted } },
          },
        }),
      }));
    }

    var mtdCanvas = document.getElementById("chart-flash-mtd");
    if (mtdCanvas && data.mtdBar) {
      var mb = data.mtdBar;
      track(new Chart(mtdCanvas, {
        type: "bar",
        data: {
          labels: mb.labels,
          datasets: [{
            data: mb.values,
            backgroundColor: [COLORS.green, COLORS.red, COLORS.red, COLORS.accent],
            borderRadius: 8,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return fmtMoney(ctx.parsed.y, currency); },
              },
            },
          }),
          scales: {
            x: { grid: { display: false }, ticks: { color: COLORS.muted } },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }
  }

  function initCashShiftCharts(data) {
    if (!window.Chart || !data) return;

    var currency = data.currency || "";

    var mixCanvas = document.getElementById("chart-shift-mix");
    if (mixCanvas && data.paymentMix) {
      var mix = data.paymentMix;
      var mixTotal = mix.values.reduce(function (a, b) { return a + b; }, 0);
      if (mixTotal > 0) {
        track(new Chart(mixCanvas, {
          type: "doughnut",
          data: {
            labels: mix.labels,
            datasets: [{
              data: mix.values,
              backgroundColor: [COLORS.accent, COLORS.occupied, COLORS.purple],
              borderWidth: 2,
              borderColor: "#fff",
            }],
          },
          options: Object.assign({}, baseOptions(), {
            cutout: "58%",
            plugins: Object.assign({}, baseOptions().plugins, {
              legend: { position: "bottom" },
              tooltip: {
                callbacks: {
                  label: function (ctx) { return ctx.label + ": " + fmtMoney(ctx.parsed, currency); },
                },
              },
            }),
          }),
        }));
      }
    }

    var flowCanvas = document.getElementById("chart-shift-flow");
    if (flowCanvas && data.cashFlow) {
      var cf = data.cashFlow;
      var flowColors = [
        COLORS.muted,
        COLORS.green,
        COLORS.accentSoft,
        COLORS.red,
        COLORS.accent,
      ];
      track(new Chart(flowCanvas, {
        type: "bar",
        data: {
          labels: cf.labels,
          datasets: [{
            data: cf.values,
            backgroundColor: cf.values.map(function (_, i) {
              return flowColors[i % flowColors.length];
            }),
            borderRadius: 8,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return fmtMoney(ctx.parsed.y, currency); },
              },
            },
          }),
          scales: {
            x: { grid: { display: false }, ticks: { color: COLORS.muted } },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }

    var varCanvas = document.getElementById("chart-shift-variance");
    if (varCanvas && data.varianceHistory && data.varianceHistory.values.length) {
      var vh = data.varianceHistory;
      track(new Chart(varCanvas, {
        type: "bar",
        data: {
          labels: vh.labels,
          datasets: [{
            data: vh.values,
            backgroundColor: vh.values.map(function (v) {
              return v >= 0 ? COLORS.green + "cc" : COLORS.red + "cc";
            }),
            borderRadius: 6,
          }],
        },
        options: Object.assign({}, baseOptions(), {
          plugins: Object.assign({}, baseOptions().plugins, {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return fmtMoney(ctx.parsed.y, currency); },
              },
            },
          }),
          scales: {
            x: { grid: { display: false }, ticks: { color: COLORS.muted } },
            y: {
              grid: { color: "rgba(26, 20, 16, 0.06)" },
              ticks: {
                color: COLORS.muted,
                callback: function (v) { return fmtMoney(v, ""); },
              },
            },
          },
        }),
      }));
    }
  }

  function initCharts() {
    destroyCharts();
    var dashEl = document.getElementById("chart-data-dashboard");
    if (dashEl && dashEl.textContent) {
      try {
        initDashboardCharts(JSON.parse(dashEl.textContent));
      } catch (e) { /* ignore */ }
    }
    var pnlEl = document.getElementById("chart-data-pnl");
    if (pnlEl && pnlEl.textContent) {
      try {
        initPnlCharts(JSON.parse(pnlEl.textContent));
      } catch (e) { /* ignore */ }
    }
    var flashEl = document.getElementById("chart-data-flash");
    if (flashEl && flashEl.textContent) {
      try {
        initFlashCharts(JSON.parse(flashEl.textContent));
      } catch (e) { /* ignore */ }
    }
    var shiftEl = document.getElementById("chart-data-cash-shift");
    if (shiftEl && shiftEl.textContent) {
      try {
        initCashShiftCharts(JSON.parse(shiftEl.textContent));
      } catch (e) { /* ignore */ }
    }
  }

  window.RivojCharts = { init: initCharts, destroy: destroyCharts };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCharts);
  } else {
    initCharts();
  }
  document.addEventListener("spa:navigated", initCharts);
})();
