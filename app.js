/**
 * Định biên Giảng viên UEH — Dashboard App
 * Loads data from DATA_INIT (data.js) or data.json, renders charts, tables, and summary cards.
 */

// ============================================
// STATE
// ============================================
let DATA = null;
let ORIGINAL_DATA = null;          // bản sao số liệu gốc để khôi phục
let currentTab = 'overview';
let sortColumn = null;
let sortDir = 'desc';
let searchTerm = '';

let chartInstances = {};
const editedCells = new Set();     // khóa: `${don_vi} ${colKey}` các ô đã sửa

// Hiển thị số cho ô CHỈNH SỬA (không nhóm hàng nghìn, dễ sửa)
function fmtEdit(v) {
  if (v === null || v === undefined || isNaN(v)) return '0';
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
}

// Đọc số người dùng nhập (chấp nhận cả định dạng Việt: 1.234,5)
function parseEdit(text) {
  let s = String(text).trim().replace(/[^\d.,\-]/g, '');
  if (s.includes('.') && s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (s.includes(',')) s = s.replace(',', '.');
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  loadData();
});

async function loadData() {
  try {
    // Ưu tiên dữ liệu nhúng sẵn từ data.js (DATA_INIT) — chạy được khi mở file://
    if (typeof DATA_INIT !== 'undefined' && DATA_INIT) {
      DATA = DATA_INIT;
    } else {
      // Fallback: tải data.json (cần chạy qua web server vì fetch không hỗ trợ file://)
      const res = await fetch('data.json');
      if (!res.ok) throw new Error(`HTTP ${res.status} khi tải data.json`);
      DATA = await res.json();
    }
    if (!DATA || !DATA.summary || !Array.isArray(DATA.khoa_data)) {
      throw new Error('Dữ liệu không hợp lệ (thiếu summary/khoa_data).');
    }
    ORIGINAL_DATA = JSON.parse(JSON.stringify(DATA.khoa_data));  // chốt bản gốc
    hideLoading();
    setupConfigSync();
    recalculateData();
    renderAll();
  } catch (err) {
    document.getElementById('loading-screen').innerHTML =
      `<div style="color:#ef4444;text-align:center;padding:2rem;">
        <h2>Lỗi tải dữ liệu</h2>
        <p>${err.message}</p>
        <p style="margin-top:1rem;color:#94a3b8;">Hãy chạy <code>python3 pipeline.py</code> để sinh data.js/data.json, rồi mở lại index.html.</p>
      </div>`;
  }
}

function hideLoading() {
  const el = document.getElementById('loading-screen');
  el.classList.add('hidden');
  setTimeout(() => el.style.display = 'none', 500);
}

function renderAll() {
  renderDateInfo();
  renderSummaryCards();
  renderCharts();
  renderTable();
  renderNotes();
  renderConfig();
  setupEventListeners();
}

// ============================================
// DATE INFO
// ============================================
function renderDateInfo() {
  const now = new Date();
  const opts = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
  document.getElementById('date-info').textContent =
    `Cập nhật: ${now.toLocaleDateString('vi-VN', opts)}`;
}

// ============================================
// SUMMARY CARDS WITH ANIMATED COUNTERS
// ============================================
function renderSummaryCards() {
  const s = DATA.summary;

  animateCounter('val-sv', s.tong_sv_quy_doi, 1);
  animateCounter('val-fte', s.tong_fte_hien_co, 1);
  animateCounter('val-ratio', s.ty_le_sv_gv_hien_tai, 1);
  animateCounter('val-fte-can', s.tong_fte_can, 0);
  animateCounter('val-tuyen', s.tong_de_xuat_tuyen, 0);

  // Color the ratio card based on value
  const ratioCard = document.getElementById('card-ratio');
  if (s.ty_le_sv_gv_hien_tai > 40) {
    document.getElementById('sub-ratio').innerHTML =
      `<span style="color:var(--accent-red);"><i class="fa-solid fa-triangle-exclamation"></i> Vượt chuẩn ${(s.ty_le_sv_gv_hien_tai / 40 * 100 - 100).toFixed(0)}%</span>`;
  }

  // FTE deficit
  const deficit = s.tong_fte_can - s.tong_fte_hien_co;
  document.getElementById('sub-fte').textContent = `Thiếu ${deficit.toFixed(0)} GV Quy đổi so với chuẩn`;
}

function animateCounter(elementId, target, decimals) {
  const el = document.getElementById(elementId);
  const duration = 1500;
  const start = 0;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + (target - start) * eased;

    el.textContent = formatNumber(current, decimals);

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.textContent = formatNumber(target, decimals);
    }
  }

  requestAnimationFrame(update);
}

function formatNumber(num, decimals = 0) {
  return num.toLocaleString('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

// ============================================
// HỆ ĐÀO TẠO CHART
// ============================================
function renderHeDaoTaoChart() {
  const ctx = document.getElementById('chart-he-dao-tao').getContext('2d');
  
  let sumCQ = 0, sumVLVH = 0, sumCTLK = 0, sumThS = 0, sumTS = 0;

  DATA.khoa_data.forEach(row => {
    sumCQ += (row.sv_cq || 0);
    sumVLVH += (row.sv_vlvh || 0);
    sumCTLK += (row.sv_ctlk || 0);
    sumThS += (row.sv_ths || 0);
    sumTS += (row.sv_ts || 0);
  });

  const dataMap = {
    'Chính quy': sumCQ,
    'Vừa làm vừa học': sumVLVH,
    'Chương trình liên kết': sumCTLK,
    'Thạc sĩ': sumThS,
    'Tiến sĩ': sumTS
  };
  
  const labels = [];
  const values = [];
  const colors = [];
  
  const colorMap = {
    'Chính quy': '#005D69',
    'Vừa làm vừa học': '#2A9DAE',
    'Chương trình liên kết': '#E0A23C',
    'Thạc sĩ': '#F36F32',
    'Tiến sĩ': '#00424B'
  };
  
  for (const [key, val] of Object.entries(dataMap)) {
    if (val > 0) {
      labels.push(key);
      values.push(val);
      colors.push(colorMap[key]);
    }
  }

  if (chartInstances.heDaoTao) chartInstances.heDaoTao.destroy();
  chartInstances.heDaoTao = new Chart(ctx, {
    type: 'pie',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#ffffff',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right' },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.raw.toLocaleString()} người`
          }
        }
      }
    }
  });
}

// ============================================
// HỌC HÀM / HỌC VỊ CHART
// ============================================
// ============================================
// CHARTS
// ============================================
function renderCharts() {
  Chart.defaults.color = '#56707a';
  Chart.defaults.borderColor = 'rgba(0,50,58,0.08)';
  Chart.defaults.font.family = 'Inter';

  renderBarChart();
  renderRatioChart();
  renderHeDaoTaoChart();
  renderHocHamChart();
  renderNhomChart();
  renderRecruitmentSplitChart();
}

function renderBarChart() {
  const ctx = document.getElementById('chart-sv-fte').getContext('2d');
  const top12 = DATA.khoa_data.slice(0, 12);
  const labels = top12.map(k => shortenName(k.don_vi));

  if (chartInstances.bar) chartInstances.bar.destroy();
  chartInstances.bar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'SV Quy đổi',
          data: top12.map(k => k.sv_quy_doi),
          backgroundColor: 'rgba(0, 93, 105, 0.75)',
          borderColor: 'rgba(0, 93, 105, 1)',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.7,
        },
        {
          label: 'GV Quy đổi Hiện có (×40)',
          data: top12.map(k => k.fte_hien_co * 40),
          backgroundColor: 'rgba(243, 111, 50, 0.65)',
          borderColor: 'rgba(243, 111, 50, 1)',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.7,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { padding: 16, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              if (ctx.datasetIndex === 1) {
                return `GV Quy đổi: ${(ctx.raw / 40).toFixed(1)} (capacity: ${ctx.raw.toFixed(0)} SV)`;
              }
              return `SV Quy đổi: ${ctx.raw.toFixed(0)}`;
            }
          }
        }
      },
      scales: {
        y: { beginAtZero: true, grid: { color: 'rgba(0,50,58,0.07)' } },
        x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 30, font: { size: 10 } } }
      }
    }
  });
}

function renderRatioChart() {
  const ctx = document.getElementById('chart-ratio-khoa').getContext('2d');
  const sorted = [...DATA.khoa_data]
    .filter(k => k.fte_hien_co > 0)
    .sort((a, b) => b.ty_le_sv_gv_hien_tai - a.ty_le_sv_gv_hien_tai)
    .slice(0, 15);
  const labels = sorted.map(k => shortenName(k.don_vi));

  if (chartInstances.ratio) chartInstances.ratio.destroy();
  chartInstances.ratio = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Tỷ lệ SV/GV',
        data: sorted.map(k => k.ty_le_sv_gv_hien_tai),
        backgroundColor: sorted.map(k =>
          k.ty_le_sv_gv_hien_tai > 80 ? 'rgba(214, 69, 69, 0.78)' :
          k.ty_le_sv_gv_hien_tai > 40 ? 'rgba(243, 111, 50, 0.78)' :
          'rgba(46, 139, 111, 0.78)'
        ),
        borderColor: sorted.map(k =>
          k.ty_le_sv_gv_hien_tai > 80 ? '#D64545' :
          k.ty_le_sv_gv_hien_tai > 40 ? '#F36F32' :
          '#2E8B6F'
        ),
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `SV/GV: ${ctx.raw} (chuẩn ≤ 40)`
          }
        },
        annotation: undefined
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(0,50,58,0.07)' },
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 10 } }
        }
      }
    },
    plugins: [{
      id: 'thresholdLine',
      afterDraw(chart) {
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        const x = xScale.getPixelForValue(40);
        const ctx = chart.ctx;
        ctx.save();
        ctx.strokeStyle = '#005D69';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(x, yScale.top);
        ctx.lineTo(x, yScale.bottom);
        ctx.stroke();
        ctx.fillStyle = '#005D69';
        ctx.font = '10px Inter';
        ctx.fillText('Chuẩn = 40', x + 4, yScale.top + 12);
        ctx.restore();
      }
    }]
  });
}

function renderHocHamChart() {
  const ctx = document.getElementById('chart-hoc-ham').getContext('2d');
  const dist = DATA.distributions.hoc_ham_vi;
  const labelMap = { GS: 'Giáo sư', PGS: 'Phó Giáo sư', TS: 'Tiến sĩ', ThS: 'Thạc sĩ', DH: 'Đại học', Khac: 'Khác' };
  const colorMap = { GS: '#F36F32', PGS: '#F58A5B', TS: '#005D69', ThS: '#2A9DAE', DH: '#2E8B6F', Khac: '#93a7ad' };
  const order = ['GS', 'PGS', 'TS', 'ThS', 'DH', 'Khac'];
  const labels = order.filter(k => dist[k]).map(k => labelMap[k]);
  const values = order.filter(k => dist[k]).map(k => dist[k]);
  const colors = order.filter(k => dist[k]).map(k => colorMap[k]);

  if (chartInstances.hocHam) chartInstances.hocHam.destroy();
  chartInstances.hocHam = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + 'cc'),
        borderColor: colors,
        borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'right',
          labels: { padding: 12, usePointStyle: true, pointStyle: 'circle', font: { size: 12 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = ((ctx.raw / total) * 100).toFixed(1);
              return `${ctx.label}: ${ctx.raw} (${pct}%)`;
            }
          }
        }
      }
    }
  });
}

function renderNhomChart() {
  const ctx = document.getElementById('chart-nhom').getContext('2d');
  const dist = DATA.distributions.nhom;
  const colorMap = { '1': '#005D69', '2': '#2A9DAE', '4': '#F36F32', '5': '#7BA098' };
  const nameMap = { '1': 'Cơ hữu', '2': 'Đồng cơ hữu', '4': 'Cơ hữu kiêm QL', '5': 'Nghiên cứu sinh' };

  // Chỉ hiển thị các nhóm có dữ liệu và nằm trong nameMap (loại Nhóm 3 thỉnh giảng)
  const keys = Object.keys(dist).sort().filter(k => k in nameMap && dist[k] > 0);
  const labels = keys.map(k => nameMap[k]);
  const values = keys.map(k => dist[k]);
  const colors = keys.map(k => colorMap[k] || '#93a7ad');

  if (chartInstances.nhom) chartInstances.nhom.destroy();
  chartInstances.nhom = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + 'cc'),
        borderColor: colors,
        borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'right',
          labels: { padding: 12, usePointStyle: true, pointStyle: 'circle', font: { size: 12 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const key = Object.keys(dist).sort()[ctx.dataIndex];
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = ((ctx.raw / total) * 100).toFixed(1);
              const desc = nhomLabels[key] || '';
              return [`${ctx.label}: ${ctx.raw} (${pct}%)`, desc];
            }
          }
        }
      }
    }
  });
}

function renderRecruitmentSplitChart() {
  const ctx = document.getElementById('chart-recruitment-split').getContext('2d');

  // Lọc khoa có đề xuất tuyển > 0, sắp xếp giảm dần, top 12
  const sorted = [...DATA.khoa_data]
    .filter(k => (k.tong_de_xuat || 0) > 0)
    .sort((a, b) => (b.tong_de_xuat || 0) - (a.tong_de_xuat || 0))
    .slice(0, 12);

  const labels = sorted.map(k => shortenName(k.don_vi));
  const coHuu = sorted.map(k => k.de_xuat_co_huu || 0);
  const dongCoHuu = sorted.map(k => k.de_xuat_dong_co_huu || 0);

  if (chartInstances.recruitmentSplit) chartInstances.recruitmentSplit.destroy();
  chartInstances.recruitmentSplit = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Cơ hữu',
          data: coHuu,
          backgroundColor: 'rgba(0, 93, 105, 0.85)',
          borderColor: 'rgba(0, 93, 105, 1)',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
        },
        {
          label: 'Đồng cơ hữu',
          data: dongCoHuu,
          backgroundColor: 'rgba(243, 111, 50, 0.85)',
          borderColor: 'rgba(243, 111, 50, 1)',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
        },
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { padding: 14, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} người`,
            footer: (items) => {
              const total = items.reduce((s, i) => s + (i.raw || 0), 0);
              return `Tổng tuyển: ${total} người`;
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true,
          beginAtZero: true,
          grid: { color: 'rgba(0,50,58,0.07)' },
          ticks: { precision: 0 }
        },
        y: {
          stacked: true,
          grid: { display: false },
          ticks: { font: { size: 10 } }
        }
      }
    }
  });
}

// ============================================
// TABLE RENDERING
// ============================================
const TABLE_CONFIGS = {
  overview: {
    columns: [
      { key: 'don_vi', label: 'Đơn vị', type: 'text' },
      { key: 'sv_quy_doi', label: 'SV Quy đổi', type: 'num', cls: 'highlight-cyan' },
      { key: 'fte_hien_co', label: 'GV Quy đổi Hiện có', type: 'num' },
      { key: 'ty_le_sv_gv_hien_tai', label: 'Tỷ lệ SV/GV', type: 'ratio' },
      { key: 'tong_so_tiet', label: 'Tổng số tiết', type: 'num' },
      { key: 'tong_quy_gio', label: 'Quỹ giờ GV', type: 'num' },
      { key: 'tong_de_xuat', label: 'Đề xuất tuyển', type: 'num', cls: 'highlight-orange' },
      { key: 'de_xuat_co_huu', label: 'Cơ hữu', type: 'num' },
      { key: 'de_xuat_dong_co_huu', label: 'Đồng cơ hữu', type: 'num' },
      { key: 'fte_sau_tuyen', label: 'GV Quy đổi sau tuyển', type: 'num', cls: 'highlight-green' },
      { key: 'ty_le_sv_gv_sau_tuyen', label: 'Tỷ lệ sau tuyển', type: 'ratio-after' },
    ]
  },
  students: {
    columns: [
      { key: 'don_vi', label: 'Đơn vị', type: 'text' },
      { key: 'sv_cq', label: 'CQ', type: 'num', editable: true },
      { key: 'sv_vlvh', label: 'VLVH', type: 'num', editable: true },
      { key: 'sv_ctlk', label: 'CTLK', type: 'num', editable: true },
      { key: 'sv_ths', label: 'ThS (SĐH)', type: 'num', editable: true },
      { key: 'sv_ts', label: 'TS (SĐH)', type: 'num', editable: true },
      { key: 'sv_quy_doi', label: 'SV Quy đổi', type: 'num', cls: 'highlight-cyan' },
      { key: 'sv_sdh_quy_doi', label: 'SĐH Quy đổi', type: 'num' },
    ]
  },
  faculty: {
    columns: [
      { key: 'don_vi', label: 'Đơn vị', type: 'text' },
      { key: 'nhom_1', label: 'Cơ hữu', type: 'num', editable: true },
      { key: 'nhom_2', label: 'Đồng cơ hữu', type: 'num', editable: true },
      { key: 'nhom_5', label: 'NCS', type: 'num', editable: true },
      { key: 'nhom_4', label: 'Cơ hữu kiêm QL', type: 'num', editable: true },
      { key: 'sl_gs', label: 'GS', type: 'num' },
      { key: 'sl_pgs', label: 'PGS', type: 'num' },
      { key: 'sl_ts_hv', label: 'TS', type: 'num' },
      { key: 'sl_ths', label: 'ThS', type: 'num' },
      { key: 'sl_dh', label: 'ĐH', type: 'num' },
      { key: 'fte_hien_co', label: 'GV Quy đổi', type: 'num', cls: 'highlight-cyan' },
      { key: 'ts_tro_len', label: 'TS trở lên', type: 'num', editable: true },
    ]
  },
  recruitment: {
    columns: [
      { key: 'don_vi', label: 'Đơn vị', type: 'text' },
      { key: 'gv_can_de_day', label: 'Thiếu để dạy', type: 'num' },
      { key: 'khuyen_nghi_ts', label: 'Khuyến nghị TS', type: 'num' },
      { key: 'de_xuat_cuc_bo', label: 'Tuyển cục bộ', type: 'num' },
      { key: 'de_xuat_bu_chuan', label: 'Bù chuẩn', type: 'num' },
      { key: 'tong_de_xuat', label: 'TỔNG TUYỂN', type: 'num', cls: 'highlight-orange' },
      { key: 'de_xuat_co_huu', label: 'Cơ hữu', type: 'num' },
      { key: 'de_xuat_dong_co_huu', label: 'Đồng cơ hữu', type: 'num' },
      { key: 'ty_le_sv_gv_hien_tai', label: 'SV/GV Hiện tại', type: 'ratio' },
      { key: 'ty_le_sv_gv_sau_tuyen', label: 'SV/GV Sau tuyển', type: 'ratio-after' },
    ]
  }
};

function renderTable() {
  const config = TABLE_CONFIGS[currentTab];
  let data = getFilteredData();

  // Sort
  if (sortColumn) {
    data.sort((a, b) => {
      const va = a[sortColumn];
      const vb = b[sortColumn];
      if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortDir === 'asc' ? va - vb : vb - va;
    });
  }

  // Render header
  const thead = document.getElementById('table-head');
  thead.innerHTML = `<tr>${config.columns.map(col =>
    `<th data-col="${col.key}" class="${sortColumn === col.key ? 'sorted' : ''}">${col.label}<span class="sort-indicator"><i class="fa-solid ${sortColumn === col.key ? (sortDir === 'asc' ? 'fa-sort-up' : 'fa-sort-down') : 'fa-sort'}"></i></span></th>`
  ).join('')}</tr>`;

  // Render body
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = data.map(row => {
    const cells = config.columns.map(col => {
      const val = row[col.key];
      switch (col.type) {
        case 'text':
          return `<td title="${val}">${val}</td>`;
        case 'num': {
          const marked = editedCells.has(`${row.don_vi} ${col.key}`) ? ' cell-edited' : '';
          if (col.editable) {
            return `<td class="num editable${marked} ${col.cls || ''}" contenteditable="true" `
              + `data-key="${col.key}" data-donvi="${String(row.don_vi).replace(/"/g, '&quot;')}" `
              + `inputmode="decimal" title="Bấm để chỉnh sửa">${fmtEdit(val)}</td>`;
          }
          return `<td class="num${marked} ${col.cls || ''}">${formatNumber(val, Number.isInteger(val) ? 0 : 1)}</td>`;
        }
        case 'ratio':
          return `<td class="num ${val > 80 ? 'highlight-red' : val > 40 ? 'highlight-orange' : 'highlight-green'}">${val}<div class="ratio-bar"><div class="fill ${val > 80 ? 'danger' : val > 40 ? 'warn' : 'ok'}" style="width:${Math.min(val / 200 * 100, 100)}%"></div></div></td>`;
        case 'ratio-after':
          return `<td class="num ${val > 40 ? 'highlight-orange' : 'highlight-green'}">${val}</td>`;
        case 'badge':
          return val === 'CANH BAO'
            ? `<td><span class="badge warning"><i class="fa-solid fa-triangle-exclamation"></i> Cảnh báo</span></td>`
            : `<td><span class="badge ok"><i class="fa-solid fa-check"></i> Đạt</span></td>`;
        default:
          return `<td>${val}</td>`;
      }
    });
    return `<tr>${cells.join('')}</tr>`;
  }).join('');

  // Add totals row
  if (data.length > 0) {
    const totalsRow = config.columns.map(col => {
      if (col.key === 'don_vi') return `<td style="font-weight:700;color:var(--accent-cyan);">TỔNG CỘNG</td>`;
      if (col.type === 'num') {
        const sum = data.reduce((s, r) => s + (r[col.key] || 0), 0);
        return `<td class="num" style="font-weight:700;color:var(--accent-cyan);">${formatNumber(sum, Number.isInteger(sum) ? 0 : 1)}</td>`;
      }
      if (col.type === 'ratio') {
        const totalSV = data.reduce((s, r) => s + r.sv_quy_doi, 0);
        const totalFTE = data.reduce((s, r) => s + r.fte_hien_co, 0);
        const ratio = totalFTE > 0 ? (totalSV / totalFTE).toFixed(1) : '—';
        return `<td class="num" style="font-weight:700;color:var(--accent-cyan);">${ratio}</td>`;
      }
      if (col.type === 'ratio-after') {
        const totalSV = data.reduce((s, r) => s + r.sv_quy_doi, 0);
        const totalFTE = data.reduce((s, r) => s + r.fte_sau_tuyen, 0);
        const ratio = totalFTE > 0 ? (totalSV / totalFTE).toFixed(1) : '—';
        return `<td class="num" style="font-weight:700;color:var(--accent-cyan);">${ratio}</td>`;
      }
      return `<td></td>`;
    }).join('');
    tbody.innerHTML += `<tr style="border-top:2px solid var(--accent-cyan);background:rgba(0,93,105,0.06);">${totalsRow}</tr>`;
  }
}

function getFilteredData() {
  if (!searchTerm) return [...DATA.khoa_data];
  const term = searchTerm.toLowerCase();
  return DATA.khoa_data.filter(k =>
    k.don_vi.toLowerCase().includes(term)
  );
}

// ============================================
// NOTES
// ============================================
function renderNotes() {
  const list = document.getElementById('notes-list');
  const c = DATA.config.constants;
  const notes = [
    ...DATA.notes,
    `Tỷ lệ SV/GV chuẩn toàn trường: ≤ ${c.ty_le_sv_gv_chuan}.`,
    `Quỹ giờ giảng: GV cơ hữu ${c.gio_nhom_1} tiết/năm • GV đồng cơ hữu ${c.gio_nhom_2} tiết/năm • GV thỉnh giảng ${c.gio_nhom_3} tiết/năm • GV kiêm nhiệm quản lý ${c.gio_nhom_4} tiết/năm.`,
    `Định mức hướng dẫn sau đại học: tối đa ${c.max_sdh_per_ts} học viên ThS/NCS quy đổi cho mỗi Tiến sĩ.`
  ];

  list.innerHTML = notes.map(n =>
    `<li><span class="note-icon"><i class="fa-solid fa-circle-check"></i></span>${n}</li>`
  ).join('');
}

// ============================================
// CONFIG TABLES
// ============================================
function renderConfig() {
  // FTE weights
  const fteBody = document.getElementById('config-fte-body');
  const fteLabels = { GS: 'Giáo sư (GS)', PGS: 'Phó Giáo sư (PGS)', TS: 'Tiến sĩ (TS)', ThS: 'Thạc sĩ (ThS)', 'ĐH': 'Đại học (ĐH)', Khac: 'Khác' };
  fteBody.innerHTML = Object.entries(DATA.config.fte_weights).map(([k, v]) =>
    `<tr><td>${fteLabels[k] || k}</td><td class="num">${v}</td></tr>`
  ).join('');

  // Student weights
  const svBody = document.getElementById('config-sv-body');
  const svLabels = { CQ: 'Chính quy (CQ)', VLVH: 'Vừa làm vừa học (VLVH)', CTLK: 'Chương trình liên kết (CTLK)', ThS: 'Thạc sĩ (ThS)', TS: 'Tiến sĩ (TS)' };
  svBody.innerHTML = Object.entries(DATA.config.student_weights).map(([k, v]) =>
    `<tr><td>${svLabels[k] || k}</td><td class="num">${v}</td></tr>`
  ).join('');

  // Nhom labels (hiển thị TÊN nhóm, không dùng số)
  const nhomNames = { '1': 'Cơ hữu', '2': 'Đồng cơ hữu', '4': 'Cơ hữu kiêm QL', '5': 'Nghiên cứu sinh' };
  const nhomBody = document.getElementById('config-nhom-body');
  nhomBody.innerHTML = Object.entries(DATA.config.nhom_labels).map(([k, v]) =>
    `<tr><td style="font-weight:600;">${nhomNames[k] || k}</td><td>${v}</td></tr>`
  ).join('');
}

// ============================================
// EVENT LISTENERS
// ============================================
function setupEventListeners() {
  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTab = btn.dataset.tab;
      sortColumn = null;
      sortDir = 'desc';
      renderTable();
    });
  });

  // Search
  document.getElementById('search-input').addEventListener('input', (e) => {
    searchTerm = e.target.value;
    renderTable();
  });

  // Column sorting
  document.getElementById('table-head').addEventListener('click', (e) => {
    const th = e.target.closest('th');
    if (!th) return;
    const col = th.dataset.col;
    if (sortColumn === col) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = col;
      sortDir = 'desc';
    }
    renderTable();
  });

  // Export CSV
  document.getElementById('btn-export').addEventListener('click', exportCSV);

  // Chỉnh sửa ô dữ liệu đầu vào (mô phỏng)
  const tbody = document.getElementById('table-body');
  tbody.addEventListener('focusout', (e) => {
    const td = e.target.closest('td.editable');
    if (td) commitEdit(td);
  });
  tbody.addEventListener('keydown', (e) => {
    const td = e.target.closest('td.editable');
    if (!td) return;
    if (e.key === 'Enter') { e.preventDefault(); td.blur(); }
    else if (e.key === 'Escape') { e.preventDefault(); renderTable(); }
  });

  // Khôi phục dữ liệu gốc
  document.getElementById('btn-reset').addEventListener('click', () => {
    if (!ORIGINAL_DATA) return;
    DATA.khoa_data = JSON.parse(JSON.stringify(ORIGINAL_DATA));
    editedCells.clear();
    recalculateData();
    renderSummaryCards();
    renderCharts();
    renderTable();
  });
}

// FTE bổ sung khi user thêm/bớt 1 nhân sự ở mỗi nhóm (mô phỏng tuyển mới).
// Công thức: FTE = hệ_số_phân_nhóm × hệ_số_học_vị_mặc định_của_nhóm
//   Cơ hữu (1)   : 1.0 × 1.0  = 1.0    (mặc định tuyển TS)
//   Đồng cơ hữu (2): 0.5 × 1.0 = 0.5
//   Kiêm QL (4)  : 1.0 × 1.0  = 1.0
//   NCS (5)      : 1.0 × 0.75 = 0.75  (học vị chuẩn hóa ThS)
const NHOM_FTE = { nhom_1: 1.0, nhom_2: 0.5, nhom_4: 1.0, nhom_5: 0.75 };
// Các nhóm KHÔNG mặc định +1 TS trở lên khi sửa (NCS chưa phải TS)
const NHOM_NO_TS_INC = new Set(['nhom_5']);

// Ghi nhận 1 ô vừa sửa -> cập nhật dữ liệu liên quan & tính lại toàn bộ
function commitEdit(td) {
  const key = td.dataset.key;
  const donvi = td.dataset.donvi;
  const row = DATA.khoa_data.find(r => String(r.don_vi) === donvi);
  if (!row) return;
  const newVal = parseEdit(td.textContent);
  const oldVal = row[key] || 0;
  if (newVal === oldVal) return;              // không thay đổi -> bỏ qua
  row[key] = newVal;
  editedCells.add(`${donvi} ${key}`);

  // Khi đổi số GV theo nhóm: tự cập nhật GV quy đổi (FTE) và TS trở lên.
  // Mặc định mỗi nhân sự tăng/giảm là 1 người trình độ TS trở lên,
  // TRỪ Nhóm 5 (NCS) — họ chưa phải Tiến sĩ.
  if (key in NHOM_FTE) {
    const delta = newVal - oldVal;
    row.fte_hien_co = Math.max(0, (row.fte_hien_co || 0) + delta * NHOM_FTE[key]);
    editedCells.add(`${donvi} fte_hien_co`);
    if (!NHOM_NO_TS_INC.has(key)) {
      row.ts_tro_len = Math.max(0, (row.ts_tro_len || 0) + delta);
      editedCells.add(`${donvi} ts_tro_len`);
    }
  }

  recalculateData();
  renderSummaryCards();
  renderCharts();
  renderTable();
}

// ============================================
// EXPORT CSV
// ============================================
function exportCSV() {
  const config = TABLE_CONFIGS[currentTab];
  const data = getFilteredData();
  const BOM = '\uFEFF';
  const header = config.columns.map(c => c.label).join(',');
  const rows = data.map(row =>
    config.columns.map(col => {
      const val = row[col.key];
      if (typeof val === 'string') return `"${val.replace(/"/g, '""')}"`;
      return val;
    }).join(',')
  );

  const csv = BOM + header + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `dinh_bien_ueh_${currentTab}_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ============================================
// HELPERS
// ============================================
function shortenName(name) {
  return name.replace(/^(KD|KTLQLNN|CNTK|TN)\s*-\s*/, '').replace(/^(Viện|Trung tâm)\s+/i, '');
}

// ============================================
// CONFIG SYNC & CALCULATION (REAL-TIME)
// ============================================
function setupConfigSync() {
  const syncGroup = (inputId, sliderId) => {
    const input = document.getElementById(inputId);
    const slider = document.getElementById(sliderId);
    
    const update = (val) => {
      input.value = val;
      slider.value = val;
      recalculateData();
      renderSummaryCards();
      renderCharts();
      renderTable();
    };

    input.addEventListener('input', (e) => update(e.target.value));
    slider.addEventListener('input', (e) => update(e.target.value));
  };

  syncGroup('input-gio-n1', 'slider-gio-n1');
  syncGroup('input-tyle-cohuu', 'slider-tyle-cohuu');
  syncGroup('input-gio-n4', 'slider-gio-n4');
  syncGroup('input-tyle-chuan', 'slider-tyle-chuan');
  syncGroup('input-max-sdh', 'slider-max-sdh');
}

function recalculateData() {
  const gioN1 = parseInt(document.getElementById('input-gio-n1').value) || 700;
  const gioN4 = parseInt(document.getElementById('input-gio-n4').value) || 230;
  const tyleChuan = parseInt(document.getElementById('input-tyle-chuan').value) || 40;
  const maxSdh = parseInt(document.getElementById('input-max-sdh').value) || 12;
  // Tỉ lệ cơ hữu trong tổng đề xuất tuyển (mặc định 70%)
  const tyLeCoHuu = Math.min(100, Math.max(0,
    parseInt(document.getElementById('input-tyle-cohuu').value) || 70));
  const gioN2 = gioN1 / 2;     // GV đồng cơ hữu = 50% quỹ giờ cơ hữu

  DATA.config.constants.gio_nhom_1 = gioN1;
  DATA.config.constants.gio_nhom_2 = gioN2;
  DATA.config.constants.gio_nhom_4 = gioN4;
  DATA.config.constants.ty_le_sv_gv_chuan = tyleChuan;
  DATA.config.constants.max_sdh_per_ts = maxSdh;
  DATA.config.constants.ty_le_co_huu = tyLeCoHuu;

  // 0. Tính lại SV quy đổi & SĐH quy đổi từ các cột thành phần (cho mô phỏng khi sửa)
  const sw = DATA.config.student_weights;
  DATA.khoa_data.forEach(row => {
    row.sv_quy_doi = (row.sv_cq || 0) * sw.CQ + (row.sv_vlvh || 0) * sw.VLVH
      + (row.sv_ctlk || 0) * sw.CTLK + (row.sv_ths || 0) * sw.ThS + (row.sv_ts || 0) * sw.TS;
    row.sv_sdh_quy_doi = (row.sv_ths || 0) * sw.ThS + (row.sv_ts || 0) * sw.TS;
  });

  DATA.khoa_data.forEach(row => {
    // 1. Tính thiếu giờ (Nhóm 5 NCS không đóng góp giờ dạy)
    row.tong_quy_gio = ((row.nhom_1 || 0) * gioN1) + ((row.nhom_2 || 0) * gioN2) + ((row.nhom_4 || 0) * gioN4);
    const gioThieu = Math.max(0, row.tong_so_tiet - row.tong_quy_gio);
    row.gv_can_de_day = Math.ceil(gioThieu / gioN1);
    
    // 2. Tính TS thiếu
    row.khuyen_nghi_ts = Math.max(0, Math.ceil((row.sv_ths + row.sv_ts) / maxSdh) - row.ts_tro_len);
    
    // 3. Đề xuất cục bộ
    row.de_xuat_cuc_bo = Math.max(row.gv_can_de_day, row.khuyen_nghi_ts);
    
    // FTE Tạm tính sau cục bộ (Hệ số TS = 1.0)
    row.fte_tam_tinh = row.fte_hien_co + row.de_xuat_cuc_bo;
    row.de_xuat_bu_chuan = 0;
  });
  
  // 4. Bù chuẩn toàn trường (Vòng lặp)
  const tongSvQuyDoiTruong = DATA.khoa_data.reduce((s, r) => s + r.sv_quy_doi, 0);
  
  // Bảo vệ loop vô tận (nếu tyle quá nhỏ)
  let loopProtect = 0;
  
  while (loopProtect < 10000) {
    loopProtect++;
    const tongFteHienTai = DATA.khoa_data.reduce((s, r) => s + r.fte_tam_tinh, 0);
    const tyLe = tongFteHienTai > 0 ? (tongSvQuyDoiTruong / tongFteHienTai) : 999;
    
    if (tyLe <= tyleChuan) break;
    
    let maxStress = -1;
    let maxIdx = -1;
    
    for (let i = 0; i < DATA.khoa_data.length; i++) {
      const fte = DATA.khoa_data[i].fte_tam_tinh || 0.1;
      const stress = DATA.khoa_data[i].sv_quy_doi / fte;
      if (stress > maxStress) {
        maxStress = stress;
        maxIdx = i;
      }
    }
    
    if (maxIdx >= 0) {
      DATA.khoa_data[maxIdx].de_xuat_bu_chuan += 1;
      DATA.khoa_data[maxIdx].fte_tam_tinh += 1;
    }
  }
  
  // 5. Cập nhật chỉ số sau tuyển
  let tongDeXuatTuyen = 0;
  let tongFteHienCo = 0;
  
  DATA.khoa_data.forEach(row => {
    row.tong_de_xuat = row.de_xuat_cuc_bo + row.de_xuat_bu_chuan;
    // Tách nhu cầu FTE theo tỉ lệ cơ hữu, rồi quy ra số người.
    // Cơ hữu = 1.0 FTE/người; Đồng cơ hữu = 0.5 FTE/người (cần gấp đôi số người).
    const fteCoHuu = row.tong_de_xuat * tyLeCoHuu / 100;
    const fteDongCoHuu = row.tong_de_xuat - fteCoHuu;
    row.de_xuat_co_huu = Math.round(fteCoHuu);
    row.de_xuat_dong_co_huu = Math.round(fteDongCoHuu / 0.5);
    row.fte_sau_tuyen = row.fte_hien_co + row.tong_de_xuat;
    row.ty_le_sv_gv_sau_tuyen = row.fte_sau_tuyen > 0 ? parseFloat((row.sv_quy_doi / row.fte_sau_tuyen).toFixed(1)) : 0;
    
    row.canh_bao_sdh = (row.fte_sau_tuyen > 0 && row.sv_sdh_quy_doi > 0 && (row.sv_sdh_quy_doi / row.fte_sau_tuyen) < (0.15 * tyleChuan)) ? 'CANH BAO' : 'Dat chuan';
    
    tongDeXuatTuyen += row.tong_de_xuat;
    tongFteHienCo += row.fte_hien_co;
  });
  
  // 6. Cập nhật Summary
  const tongFteCan = Math.ceil(tongSvQuyDoiTruong / tyleChuan);
  DATA.summary.tong_fte_hien_co = tongFteHienCo;
  DATA.summary.tong_fte_can = tongFteCan;
  DATA.summary.tong_de_xuat_tuyen = tongDeXuatTuyen;
  DATA.summary.ty_le_sv_gv_hien_tai = tongFteHienCo > 0 ? parseFloat((tongSvQuyDoiTruong / tongFteHienCo).toFixed(1)) : 0;
}
