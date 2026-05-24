# -*- coding: utf-8 -*-
"""
Định biên Giảng viên UEH — Compute Engine
==========================================
Đọc 6 sheet "có sử dụng" từ file Excel kế hoạch tuyển dụng, tính toán định biên
theo Thông tư 34 và xuất ``data.js`` + ``data.json`` cho dashboard ``index.html``.

Thường được gọi qua ``pipeline.py`` (đã dựng sẵn file gộp), nhưng cũng chạy độc
lập được:  ``python3 build_data.py [đường_dẫn_file.xlsx]``
"""
import sys
import math
import json
import os


def _ensure_utf8_stdout():
    """Đảm bảo stdout ghi UTF-8 (terminal Windows hay mặc định cp1252)."""
    try:
        enc = (sys.stdout.encoding or "").lower()
        if not enc.startswith("utf"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_ensure_utf8_stdout()

import pandas as pd
import numpy as np

# =========================================================
# 1. CẤU HÌNH THAM SỐ
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, "Duthaokehoachtuyendung2026-2030.xlsx")
# Dashboard nạp data.js (DATA_INIT, chạy được file://) và fallback fetch data.json
OUTPUT_JS = os.path.join(BASE_DIR, "data.js")
OUTPUT_JSON = os.path.join(BASE_DIR, "data.json")

SHEETS = {
    "hr_raw": "Quy mô giảng viên",
    "demand": "Phụ lục 2. DS môn học 2025",
    "students_ug": "Quy mô sinh viên",
    "students_pg": "Quy mô SĐH",
    "mapping": "Đơn vị giảng dạy",
    "ctdt": "Chuongtrinhdaotao",
}

CONSTANTS = {
    "gio_nhom_1": 700,   # Giờ/năm GV cơ hữu
    "gio_nhom_2": 350,   # Giờ/năm GV đồng cơ hữu (gán lại = 50% cơ hữu bên dưới)
    "gio_nhom_4": 230,   # Giờ/năm GV kiêm quản lý
    "ty_le_sv_gv_chuan": 40.0,
    "max_sdh_per_ts": 12.0,
    "ty_le_co_huu": 70,  # % cơ hữu trong tổng đề xuất tuyển
}
# GV đồng cơ hữu = 50% quỹ giờ cơ hữu (đồng bộ với app.js: gioN2 = gioN1/2)
CONSTANTS["gio_nhom_2"] = CONSTANTS["gio_nhom_1"] // 2

FTE_WEIGHTS = {
    "GS": 1.0, "PGS": 1.0, "TS": 1.0,
    "ThS": 0.75, "ĐH": 0.50, "Khac": 0.50,
}

# Hệ số PHÂN NHÓM của giảng viên (sẽ nhân với hệ số học hàm/học vị để ra FTE).
#   Cơ hữu (1)         = 1.0
#   Đồng cơ hữu (2)    = 0.5
#   Cơ hữu kiêm QL (4) = 1.0
#   Nghiên cứu sinh (5) = 1.0  (NCS được coi như cơ hữu, học vị mặc định ThS = 0.75)
NHOM_COEF = {1: 1.0, 2: 0.5, 4: 1.0, 5: 1.0}

# Khi GV thuộc Nhóm 5 (NCS), ta CHUẨN HÓA học vị về Thạc sĩ (0.75)
# vì NCS đang trong quá trình đào tạo TS, học vị hiện tại là ThS.
NCS_HOC_VI_COEF = 0.75

STUDENT_WEIGHTS = {
    "CQ": 1.0,
    "VLVH": 0.8,
    "CTLK": 0.75,   # Chương trình liên kết (trước đây là TXTT)
    "ThS": 1.5,
    "TS": 2.0,
}

# =========================================================
# 2. EXTRACT
# =========================================================
def extract_data(file_path=None):
    file_path = file_path or FILE_PATH
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Khong tim thay file Excel: {file_path}")
    print(f"Dang tai du lieu tu Excel: {os.path.basename(file_path)}")

    try:
        all_sheets = pd.read_excel(file_path, sheet_name=list(SHEETS.values()),
                                   engine='openpyxl')
    except ValueError as e:
        # pandas báo lỗi khi thiếu sheet -> liệt kê sheet còn thiếu cho dễ sửa
        try:
            available = pd.ExcelFile(file_path, engine='openpyxl').sheet_names
        except Exception:
            available = []
        missing = [s for s in SHEETS.values() if s not in available]
        raise ValueError(
            f"File '{os.path.basename(file_path)}' thieu sheet bat buoc: {missing}. "
            f"Cac sheet hien co: {available}"
        ) from e

    df_hr = all_sheets[SHEETS["hr_raw"]]
    df_demand = all_sheets[SHEETS["demand"]]
    df_ug = all_sheets[SHEETS["students_ug"]]
    df_pg = all_sheets[SHEETS["students_pg"]]
    df_mapping = all_sheets[SHEETS["mapping"]]
    df_ctdt = all_sheets[SHEETS["ctdt"]]

    # Chuẩn hóa tên cột mapping (chỉ giữ 2 cột đầu nếu file dư cột)
    df_mapping = df_mapping.iloc[:, :2].copy()
    df_mapping.columns = ['Mã quản lý', 'Đơn vị giảng dạy']

    return df_hr, df_demand, df_ug, df_pg, df_mapping, df_ctdt


# =========================================================
# 3. TRANSFORM
# =========================================================
def transform_data(df_hr, df_demand, df_ug, df_pg, df_mapping, df_ctdt):
    print("Dang xu ly va tinh toan...")

    # ---- LUỒNG 1: NHU CẦU GIỜ DẠY ----
    df_demand.columns = df_demand.columns.str.strip()
    df_demand = df_demand[
        df_demand['Đơn vị phụ trách'].notna() &
        (df_demand['Đơn vị phụ trách'].astype(str).str.strip().str.upper() != '#N/A') &
        (df_demand['Đơn vị phụ trách'].astype(str).str.strip() != '')
    ].copy()
    df_demand['Tổng số tiết'] = pd.to_numeric(
        df_demand['Tổng số tiết'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)

    df_cau_gio = df_demand.groupby('Đơn vị phụ trách').agg(
        Tong_so_tiet_thuc_te=('Tổng số tiết', 'sum')
    ).reset_index().rename(columns={'Đơn vị phụ trách': 'Don_vi_quan_ly'})

    # === XÁC ĐỊNH DANH SÁCH KHOA/VIỆN TÍNH ĐỊNH BIÊN ===
    # Lấy từ sheet demand với điều kiện Ghi chú = "Tính định biên"
    mask_dinh_bien = df_demand['Ghi chú'].astype(str).str.strip() == 'Tính định biên'
    danh_sach_khoa = df_demand.loc[mask_dinh_bien, 'Đơn vị phụ trách'].dropna().unique().tolist()
    danh_sach_khoa = [k for k in danh_sach_khoa
                      if str(k).strip() != '' and '#N/A' not in str(k)]

    # === CHUẨN HÓA TÊN ĐƠN VỊ TOÀN BỘ DỮ LIỆU ===
    # Tạo bảng lookup: lowercase → tên chuẩn (lấy từ demand sheet)
    # Tên chuẩn = tên trong danh_sach_khoa (Ghi chú = Tính định biên)
    canonical_map = {}  # lowercase -> canonical name
    for name in danh_sach_khoa:
        canonical_map[name.lower()] = name
    # Thêm tất cả tên đơn vị từ demand (kể cả không tính định biên)
    for name in df_demand['Đơn vị phụ trách'].dropna().unique():
        key = str(name).lower()
        if key not in canonical_map:
            canonical_map[key] = str(name)

    def normalize_unit(name):
        """Chuẩn hóa tên đơn vị về dạng canonical."""
        if pd.isna(name) or str(name).strip() == '':
            return name
        key = str(name).strip().lower()
        return canonical_map.get(key, str(name).strip())

    # Áp dụng chuẩn hóa cho TẤT CẢ cột đơn vị trong mọi dataframe
    df_demand['Đơn vị phụ trách'] = df_demand['Đơn vị phụ trách'].apply(normalize_unit)
    df_ug.columns = df_ug.columns.str.strip()
    if 'Khoa/Viện quản lý' in df_ug.columns:
        df_ug['Khoa/Viện quản lý'] = df_ug['Khoa/Viện quản lý'].apply(normalize_unit)
    df_pg.columns = df_pg.columns.str.strip()
    if 'Đơn vị quản lý' in df_pg.columns:
        df_pg['Đơn vị quản lý'] = df_pg['Đơn vị quản lý'].apply(normalize_unit)
    df_ctdt.columns = df_ctdt.columns.str.strip()
    if 'Khoa/Viện' in df_ctdt.columns:
        df_ctdt['Khoa/Viện'] = df_ctdt['Khoa/Viện'].apply(normalize_unit)
    df_hr.columns = df_hr.columns.str.strip()
    if 'Đơn vị' in df_hr.columns:
        df_hr['Đơn vị'] = df_hr['Đơn vị'].apply(normalize_unit)
    if 'Đơn vị giảng dạy' in df_mapping.columns:
        df_mapping['Đơn vị giảng dạy'] = df_mapping['Đơn vị giảng dạy'].apply(normalize_unit)

    danh_sach_khoa_lower = set(k.lower() for k in danh_sach_khoa)
    print(f"  Danh sach khoa tinh dinh bien ({len(danh_sach_khoa)}):")
    for k in sorted(danh_sach_khoa):
        print(f"    - {k}")

    # ---- LUỒNG 2: QUY MÔ SINH VIÊN ĐẠI HỌC ----
    df_ug.columns = df_ug.columns.str.strip()

    # ISB - Chính quy tính vào CQ (hệ số 1.0)
    cot_cq = ['ISB - Chính quy', 'Chính quy', 'Văn bằng 2 chính quy', 'Liên thông chính quy']
    cot_vlvh = [
        'Văn bằng 1 - Vừa làm vừa học', 'Văn bằng 2 - Vừa làm vừa học',
        'Liên thông cao đẳng - Vừa làm vừa học', 'Liên thông trung cấp - Vừa làm vừa học'
    ]
    # Không có cột TXTT trong dữ liệu hiện tại
    cot_txtt = ['Đào tạo từ xa', 'Văn bằng 2 từ xa']

    for cot in cot_cq + cot_vlvh + cot_txtt:
        if cot in df_ug.columns:
            df_ug[cot] = pd.to_numeric(
                df_ug[cot].astype(str).str.replace(',', ''), errors='coerce'
            ).fillna(0)
        else:
            df_ug[cot] = 0

    df_ug['Tong_CQ'] = df_ug[cot_cq].sum(axis=1)
    df_ug['Tong_VLVH'] = df_ug[cot_vlvh].sum(axis=1)
    df_ug['Tong_TXTT'] = df_ug[cot_txtt].sum(axis=1)

    df_sv_khoa = df_ug.groupby('Khoa/Viện quản lý').agg(
        Quy_mo_CQ=('Tong_CQ', 'sum'),
        Quy_mo_VLVH=('Tong_VLVH', 'sum'),
        Quy_mo_TXTT=('Tong_TXTT', 'sum'),
    ).reset_index().rename(columns={'Khoa/Viện quản lý': 'Don_vi_quan_ly'})

    # ---- LUỒNG 3: QUY MÔ SĐH (PHÂN BỔ THEO CHƯƠNG TRÌNH ĐÀO TẠO) ----
    # Thay vì dùng cột "Đơn vị quản lý" nhập tay trong sheet SĐH,
    # ta dùng sheet CTDT để xác định mỗi ngành SĐH có bao nhiêu CT
    # ở mỗi Khoa/Viện, rồi chia đều SV theo tỷ lệ số CT.
    df_pg.columns = df_pg.columns.str.strip()
    df_pg['Quy_mô_ThS'] = pd.to_numeric(
        df_pg['Quy_mô_ThS'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)
    df_pg['Quy_mô_TS'] = pd.to_numeric(
        df_pg['Quy_mô_TS'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)

    # Lọc các CT SĐH từ sheet CTDT
    df_ctdt.columns = df_ctdt.columns.str.strip()
    df_ctdt_sdh = df_ctdt[
        df_ctdt['Trình độ'].isin(['Thạc sĩ', 'Tiến sĩ']) &
        df_ctdt['Khoa/Viện'].notna()
    ].copy()

    # Đếm số CT ThS/TS của mỗi ngành tại mỗi Khoa/Viện
    ct_ths = df_ctdt_sdh[df_ctdt_sdh['Trình độ'] == 'Thạc sĩ'].groupby(
        ['Tên ngành đào tạo', 'Khoa/Viện']
    ).size().reset_index(name='So_CT_ThS')
    ct_ts = df_ctdt_sdh[df_ctdt_sdh['Trình độ'] == 'Tiến sĩ'].groupby(
        ['Tên ngành đào tạo', 'Khoa/Viện']
    ).size().reset_index(name='So_CT_TS')

    # Phân bổ SV ThS theo tỷ lệ số CT
    sdh_rows = []
    for _, pg_row in df_pg.iterrows():
        nganh = pg_row['Ngành']
        quy_mo_ths = pg_row['Quy_mô_ThS']
        quy_mo_ts = pg_row['Quy_mô_TS']

        # Phân bổ ThS
        if quy_mo_ths > 0:
            ct_match = ct_ths[ct_ths['Tên ngành đào tạo'] == nganh]
            if len(ct_match) > 0:
                tong_ct = ct_match['So_CT_ThS'].sum()
                for _, ct_row in ct_match.iterrows():
                    ty_le = ct_row['So_CT_ThS'] / tong_ct
                    sdh_rows.append({
                        'Don_vi_quan_ly': ct_row['Khoa/Viện'],
                        'Quy_mo_ThS': round(quy_mo_ths * ty_le),
                        'Quy_mo_TS': 0,
                    })
            else:
                # Fallback: dùng Đơn vị quản lý gốc nếu không tìm thấy CT
                sdh_rows.append({
                    'Don_vi_quan_ly': pg_row['Đơn vị quản lý'],
                    'Quy_mo_ThS': quy_mo_ths,
                    'Quy_mo_TS': 0,
                })
                print(f"  [WARN] Nganh ThS '{nganh}' khong tim thay trong CTDT, dung DV goc: {pg_row['Đơn vị quản lý']}")

        # Phân bổ TS
        if quy_mo_ts > 0:
            ct_match = ct_ts[ct_ts['Tên ngành đào tạo'] == nganh]
            if len(ct_match) > 0:
                tong_ct = ct_match['So_CT_TS'].sum()
                for _, ct_row in ct_match.iterrows():
                    ty_le = ct_row['So_CT_TS'] / tong_ct
                    sdh_rows.append({
                        'Don_vi_quan_ly': ct_row['Khoa/Viện'],
                        'Quy_mo_ThS': 0,
                        'Quy_mo_TS': round(quy_mo_ts * ty_le),
                    })
            else:
                # Fallback: dùng Đơn vị quản lý gốc
                sdh_rows.append({
                    'Don_vi_quan_ly': pg_row['Đơn vị quản lý'],
                    'Quy_mo_ThS': 0,
                    'Quy_mo_TS': quy_mo_ts,
                })
                print(f"  [WARN] Nganh TS '{nganh}' khong tim thay trong CTDT, dung DV goc: {pg_row['Đơn vị quản lý']}")

    df_sdh_distributed = pd.DataFrame(sdh_rows)
    df_sdh_khoa = df_sdh_distributed.groupby('Don_vi_quan_ly').agg(
        Quy_mo_ThS=('Quy_mo_ThS', 'sum'),
        Quy_mo_TS=('Quy_mo_TS', 'sum'),
    ).reset_index()

    # In chi tiết phân bổ SĐH
    print("\n  === PHAN BO SDH THEO CTDT ===")
    for _, r in df_sdh_khoa.iterrows():
        if r['Quy_mo_ThS'] > 0 or r['Quy_mo_TS'] > 0:
            print(f"    {r['Don_vi_quan_ly']}: ThS={r['Quy_mo_ThS']:.1f}, TS={r['Quy_mo_TS']:.1f}")
    print(f"  Tong ThS: {df_sdh_khoa['Quy_mo_ThS'].sum():.1f}, Tong TS: {df_sdh_khoa['Quy_mo_TS'].sum():.1f}")

    # ---- HỢP NHẤT SV ----
    df_master = pd.merge(df_cau_gio, df_sv_khoa, on='Don_vi_quan_ly', how='outer').fillna(0)
    df_master = pd.merge(df_master, df_sdh_khoa, on='Don_vi_quan_ly', how='outer').fillna(0)

    # Tổng SV quy đổi
    df_master['Tong_SV_quy_doi'] = (
        df_master['Quy_mo_CQ'] * STUDENT_WEIGHTS["CQ"] +
        df_master['Quy_mo_VLVH'] * STUDENT_WEIGHTS["VLVH"] +
        df_master['Quy_mo_TXTT'] * STUDENT_WEIGHTS["CTLK"] +
        df_master['Quy_mo_ThS'] * STUDENT_WEIGHTS["ThS"] +
        df_master['Quy_mo_TS'] * STUDENT_WEIGHTS["TS"]
    )

    # SV SĐH quy đổi
    df_master['SV_SDH_quy_doi'] = (
        df_master['Quy_mo_ThS'] * STUDENT_WEIGHTS["ThS"] +
        df_master['Quy_mo_TS'] * STUDENT_WEIGHTS["TS"]
    )



    # ---- LUỒNG 4: NHÂN SỰ ----
    df_hr.columns = df_hr.columns.str.strip()

    # Lọc giảng viên: Chức danh chứa "Giảng viên" hoặc = "isb"
    mask_gv = (
        df_hr['Chức danh'].astype(str).str.contains("Giảng viên", case=False, na=False) |
        (df_hr['Chức danh'].astype(str).str.strip().str.lower() == 'isb')
    )
    df_gv = df_hr[mask_gv].copy()

    # NCS toàn thời gian VẪN tính là GV với hệ số FTE = 0.75 (xử lý trong quy_doi_fte)
    gv_ncs_count = df_gv['Tình trạng làm việc'].astype(str).str.contains(
        'NCS toàn thời gian', case=False, na=False
    ).sum()
    print(f"  Luu y: {gv_ncs_count} NCS toan thoi gian - tinh nhu GV (FTE = 0.75)")

    # GV làm việc Từ xa VẪN tính vào định biên (theo yêu cầu nghiệp vụ)
    gv_tuxa_count = df_gv['Tình trạng làm việc'].astype(str).str.contains(
        'Từ xa', case=False, na=False
    ).sum()
    print(f"  Luu y: {gv_tuxa_count} GV lam viec tu xa - VAN tinh vao dinh bien")

    # Phân nhóm GV: Đơn vị in danh_sach_khoa -> Nhóm 1, else -> Nhóm 4
    # (Nhóm 2, 3 hiện tại chưa có)
    # So sánh lowercase để tránh lỗi chữ hoa/thường (vd: "Thông minh" vs "thông minh")
    df_gv['Nhóm'] = df_gv['Đơn vị'].apply(
        lambda x: 1 if str(x).lower() in danh_sach_khoa_lower else 4
    )

    df_gv['Nhóm'] = df_gv['Nhóm'].astype(int)

    # ISB → mapped vào TN - Khoa Tài năng kinh doanh
    mask_isb = df_gv['Chức danh'].astype(str).str.strip().str.lower() == 'isb'
    df_gv.loc[mask_isb, 'Nhóm'] = 1  # ISB tính là cơ hữu

    # NCS toàn thời gian → Nhóm 5 (tính như cơ hữu nhưng FTE=0.75, giờ dạy=0)
    mask_ncs_full = df_gv['Tình trạng làm việc'].astype(str).str.contains(
        'NCS toàn thời gian', case=False, na=False
    )
    df_gv.loc[mask_ncs_full, 'Nhóm'] = 5

    # Map đơn vị giảng dạy.
    # Chuẩn hóa khóa "Mã quản lý" để join ổn định bất kể Excel đọc là int/float/str
    # (vd '1307.0' (float) vs '1307' (int) phải khớp nhau).
    def _clean_id(series):
        return (series.astype(str).str.strip()
                .str.replace(r'\.0$', '', regex=True))
    df_gv['Mã quản lý'] = _clean_id(df_gv['Mã quản lý'])
    df_mapping['Mã quản lý'] = _clean_id(df_mapping['Mã quản lý'])
    df_gv = pd.merge(df_gv, df_mapping, on='Mã quản lý', how='left')

    # Xác định đơn vị giảng dạy cuối cùng
    def get_don_vi_giang_day(row):
        # ISB → TN - Khoa Tài năng kinh doanh
        if str(row.get('Chức danh', '')).strip().lower() == 'isb':
            return 'TN - Khoa Tài năng kinh doanh'
        # Nhóm 1 (cơ hữu) và Nhóm 5 (NCS): dùng Đơn vị (đơn vị quản lý chính)
        if row['Nhóm'] in (1, 5):
            return row['Đơn vị']
        # Nhóm 2, 3, 4: dùng Đơn vị giảng dạy từ mapping
        dv_gd = str(row.get('Đơn vị giảng dạy', '')).strip()
        if pd.notna(row.get('Đơn vị giảng dạy')) and dv_gd != '' and dv_gd != 'nan':
            return dv_gd
        return 'Chua phan cong'

    df_gv['Don_vi_giang_day_cuoi'] = df_gv.apply(get_don_vi_giang_day, axis=1)

    # ===== BÁO CÁO GV THIẾU MAPPING ĐƠN VỊ GIẢNG DẠY =====
    # GV nhóm 4 (đơn vị hành chính/admin) nhưng không có ánh xạ -> bị loại khỏi FTE.
    # Xuất danh sách ra CSV để bộ phận HR bổ sung mapping.
    mask_missing = (df_gv['Nhóm'] == 4) & (df_gv['Don_vi_giang_day_cuoi'] == 'Chua phan cong')
    df_missing = df_gv.loc[mask_missing, [
        'Mã quản lý', 'Họ tên', 'Đơn vị', 'Học hàm', 'Học vị',
        'Chức danh', 'Tình trạng làm việc'
    ]].copy()
    if len(df_missing) > 0:
        report_path = os.path.join(BASE_DIR, 'report_thieu_mapping.csv')
        df_missing.to_csv(report_path, index=False, encoding='utf-8-sig')
        print(f"  Bao cao thieu mapping: {os.path.basename(report_path)} ({len(df_missing)} GV)")

    # Tính FTE
    def quy_doi_fte(row):
        """
        Công thức:  FTE = hệ_số_phân_nhóm  ×  hệ_số_học_hàm/học_vị
            - hệ_số_phân_nhóm  lấy từ NHOM_COEF (cơ hữu 1.0, đồng cơ hữu 0.5, ...).
            - hệ_số_học_hàm/học_vị lấy từ FTE_WEIGHTS (GS/PGS/TS 1.0, ThS 0.75, ĐH/Khác 0.5).
        Nhóm 5 (NCS) được chuẩn hóa hệ số học vị về ThS (0.75) bất kể dữ liệu.
        """
        hoc_vi = str(row.get('Học vị', '')).strip().upper()
        hoc_ham = str(row.get('Học hàm', '')).strip().upper()
        nhom = int(row.get('Nhóm', 1))

        # Hệ số học hàm/học vị
        if nhom == 5:
            hv_coef = NCS_HOC_VI_COEF
        elif hoc_ham in ['GIÁO SƯ', 'GS']:
            hv_coef = FTE_WEIGHTS["GS"]
        elif hoc_ham in ['PHÓ GIÁO SƯ', 'PGS']:
            hv_coef = FTE_WEIGHTS["PGS"]
        elif hoc_vi in ['TIẾN SĨ', 'TS']:
            hv_coef = FTE_WEIGHTS["TS"]
        elif hoc_vi in ['THẠC SĨ', 'THS']:
            hv_coef = FTE_WEIGHTS["ThS"]
        elif hoc_vi in ['ĐẠI HỌC', 'ĐH', 'CỬ NHÂN', 'CN', 'KỸ SƯ', 'KS']:
            hv_coef = FTE_WEIGHTS["ĐH"]
        else:
            hv_coef = FTE_WEIGHTS["Khac"]

        return NHOM_COEF.get(nhom, 0.0) * hv_coef

    df_gv['FTE'] = df_gv.apply(quy_doi_fte, axis=1)
    df_gv['La_TS_tro_len'] = df_gv.apply(
        lambda row: 1 if (
            str(row.get('Học hàm', '')).upper() in ['GS', 'GIÁO SƯ', 'PGS', 'PHÓ GIÁO SƯ'] or
            str(row.get('Học vị', '')).upper() in ['TS', 'TIẾN SĨ']
        ) else 0,
        axis=1
    )

    # Tính quỹ giờ mỗi GV theo nhóm. Nhóm 5 (NCS) không tính giờ dạy.
    gio_map = {1: CONSTANTS["gio_nhom_1"], 2: CONSTANTS["gio_nhom_2"],
               4: CONSTANTS["gio_nhom_4"], 5: 0}
    df_gv['Quy_gio'] = df_gv['Nhóm'].map(gio_map).fillna(0)

    # Xác định học hàm/học vị label
    def get_hoc_ham_vi_label(row):
        hh = str(row.get('Học hàm', '')).strip()
        hv = str(row.get('Học vị', '')).strip()
        if hh.upper() in ['GIÁO SƯ', 'GS']:
            return 'GS'
        elif hh.upper() in ['PHÓ GIÁO SƯ', 'PGS']:
            return 'PGS'
        elif hv.upper() in ['TIẾN SĨ', 'TS']:
            return 'TS'
        elif hv.upper() in ['THẠC SĨ', 'THS']:
            return 'ThS'
        elif hv.upper() in ['ĐẠI HỌC', 'ĐH', 'CỬ NHÂN', 'CN']:
            return 'DH'
        else:
            return 'Khac'

    df_gv['Hoc_ham_vi_label'] = df_gv.apply(get_hoc_ham_vi_label, axis=1)

    # Gom theo đơn vị
    df_supply = df_gv.groupby('Don_vi_giang_day_cuoi').agg(
        Hien_co_FTE=('FTE', 'sum'),
        Hien_co_TS_tro_len=('La_TS_tro_len', 'sum'),
        SL_Nhom_1=('Nhóm', lambda x: (x == 1).sum()),
        SL_Nhom_2=('Nhóm', lambda x: (x == 2).sum()),
        SL_Nhom_4=('Nhóm', lambda x: (x == 4).sum()),
        SL_Nhom_5=('Nhóm', lambda x: (x == 5).sum()),
        Tong_quy_gio=('Quy_gio', 'sum'),
        SL_GS=('Hoc_ham_vi_label', lambda x: (x == 'GS').sum()),
        SL_PGS=('Hoc_ham_vi_label', lambda x: (x == 'PGS').sum()),
        SL_TS=('Hoc_ham_vi_label', lambda x: (x == 'TS').sum()),
        SL_ThS=('Hoc_ham_vi_label', lambda x: (x == 'ThS').sum()),
        SL_DH=('Hoc_ham_vi_label', lambda x: (x == 'DH').sum()),
    ).reset_index().rename(columns={'Don_vi_giang_day_cuoi': 'Don_vi_quan_ly'})

    # Merge supply vào master
    df_master = pd.merge(df_master, df_supply, on='Don_vi_quan_ly', how='outer').fillna(0)

    # Loại bỏ đơn vị rỗng/0
    df_master = df_master[
        (df_master['Don_vi_quan_ly'] != 0) &
        (df_master['Don_vi_quan_ly'].astype(str).str.strip() != '') &
        (df_master['Don_vi_quan_ly'].astype(str).str.strip() != 'Chua phan cong')
    ]

    # Chỉ giữ lại các đơn vị trong danh_sach_khoa (so sánh lowercase)
    df_master = df_master[df_master['Don_vi_quan_ly'].astype(str).str.lower().isin(danh_sach_khoa_lower)]

    return df_master, df_gv, danh_sach_khoa


# =========================================================
# 4. OPTIMIZE
# =========================================================
def optimize_multi_stage(df_master):
    print("Dang chay thuat toan toi uu...")

    gio_n1 = CONSTANTS["gio_nhom_1"]
    ty_le_chuan = CONSTANTS["ty_le_sv_gv_chuan"]
    fte_tuyen_moi = FTE_WEIGHTS["TS"]  # Giả sử tuyển mới là TS
    max_sdh = CONSTANTS["max_sdh_per_ts"]

    # GĐ1: Tính số GV thiếu để bù vô giờ giảng dựa trên quỹ giờ thực tế
    gio_n2 = CONSTANTS["gio_nhom_2"]
    gio_n4 = CONSTANTS["gio_nhom_4"]

    df_master['Tong_quy_gio_hien_co'] = (
        (df_master['SL_Nhom_1'] * gio_n1) +
        (df_master['SL_Nhom_2'] * gio_n2) +
        (df_master['SL_Nhom_4'] * gio_n4)
        # Nhóm 5 (NCS) không tính giờ dạy nên không cộng vào quỹ giờ.
    )
    df_master['Gio_thieu'] = df_master.apply(
        lambda row: max(0, row['Tong_so_tiet_thuc_te'] - row['Tong_quy_gio_hien_co']),
        axis=1
    )
    df_master['GV_can_de_day'] = (df_master['Tong_so_tiet_thuc_te'] / gio_n1).apply(math.ceil)
    df_master['GV_thieu_de_day'] = (df_master['Gio_thieu'] / gio_n1).apply(math.ceil)

    # GĐ2: Tính số TS cần tuyển để đủ hướng dẫn SĐH (chia cho max_sdh theo yêu cầu)
    df_master['Khuyen_nghi_tuyen_TS'] = df_master.apply(
        lambda row: max(0, math.ceil((row['Quy_mo_ThS'] + row['Quy_mo_TS']) / max_sdh) - row['Hien_co_TS_tro_len']),
        axis=1
    )

    # Đề xuất tuyển cục bộ = max(Thiếu giờ giảng, Thiếu TS)
    df_master['De_xuat_cuc_bo'] = df_master.apply(
        lambda row: max(row['GV_thieu_de_day'], row['Khuyen_nghi_tuyen_TS']),
        axis=1
    )

    # Tính FTE tạm tính sau cục bộ
    df_master['FTE_Tam_tinh'] = df_master['Hien_co_FTE'] + (df_master['De_xuat_cuc_bo'] * fte_tuyen_moi)

    # GĐ3: Bù chuẩn kiểm định toàn trường (Vòng lặp)
    tong_sv_truong = df_master['Tong_SV_quy_doi'].sum()
    df_master['De_xuat_bu_chuan'] = 0

    while True:
        tong_fte_tam = df_master['FTE_Tam_tinh'].sum()
        ty_le_toan_truong = tong_sv_truong / tong_fte_tam if tong_fte_tam > 0 else 999
        
        if ty_le_toan_truong <= ty_le_chuan:
            break
            
        # Nếu không đạt, tìm khoa có tỷ lệ SV/GV (chỉ số căng thẳng) cao nhất
        df_master['Chi_so_cang_thang'] = df_master['Tong_SV_quy_doi'] / df_master['FTE_Tam_tinh'].replace(0, 0.1)
        idx_max = df_master['Chi_so_cang_thang'].idxmax()
        
        # Thêm 1 giảng viên (mặc định là TS) vào khoa đó
        df_master.at[idx_max, 'De_xuat_bu_chuan'] += 1
        df_master.at[idx_max, 'FTE_Tam_tinh'] += fte_tuyen_moi

    df_master['Tong_de_xuat_tuyen'] = df_master['De_xuat_cuc_bo'] + df_master['De_xuat_bu_chuan']

    # Tỷ lệ SV/GV sau tuyển
    df_master['Ty_le_SV_GV_hien_tai'] = df_master.apply(
        lambda r: round(r['Tong_SV_quy_doi'] / r['Hien_co_FTE'], 1) if r['Hien_co_FTE'] > 0 else 0,
        axis=1
    )
    df_master['FTE_sau_tuyen'] = df_master['Hien_co_FTE'] + df_master['Tong_de_xuat_tuyen'] * fte_tuyen_moi
    df_master['Ty_le_SV_GV_sau_tuyen'] = df_master.apply(
        lambda r: round(r['Tong_SV_quy_doi'] / r['FTE_sau_tuyen'], 1) if r['FTE_sau_tuyen'] > 0 else 0,
        axis=1
    )

    # Kiểm tra ràng buộc 15% SĐH
    # Tỷ lệ: SĐH_quy_doi / FTE_sau_tuyen >= 15% * 40 = 6
    df_master['Canh_bao_SDH'] = df_master.apply(
        lambda r: 'CANH BAO' if (
            r['FTE_sau_tuyen'] > 0 and
            r['SV_SDH_quy_doi'] > 0 and
            (r['SV_SDH_quy_doi'] / r['FTE_sau_tuyen']) < (0.15 * ty_le_chuan)
        ) else 'Dat chuan',
        axis=1
    )

    # Tổng kết toàn trường
    tong_fte_hien_co = df_master['Hien_co_FTE'].sum()
    tong_de_xuat = df_master['Tong_de_xuat_tuyen'].sum()
    tong_fte_tam = df_master['FTE_Tam_tinh'].sum()
    ty_le_hien_tai = round(tong_sv_truong / tong_fte_hien_co, 1) if tong_fte_hien_co > 0 else 0
    tong_fte_can = math.ceil(tong_sv_truong / ty_le_chuan)

    print(f"\n--- KET QUA DINH BIEN TOAN TRUONG ---")
    print(f"Tong SV quy doi: {tong_sv_truong}")
    print(f"Tong FTE hien co: {tong_fte_hien_co}")
    print(f"Tong FTE can theo chuan Bo: {tong_fte_can}")
    print(f"Ty le SV/GV hien tai: {ty_le_hien_tai}")
    print(f"TONG NGUOI CAN TUYEN THEM: {tong_de_xuat} nguoi.")

    # Dọn cột tạm
    df_master.drop(columns=['FTE_Tam_tinh', 'Chi_so_cang_thang'], inplace=True, errors='ignore')

    summary = {
        "tong_sv_quy_doi": float(tong_sv_truong),
        "tong_fte_hien_co": float(tong_fte_hien_co),
        "tong_fte_can": int(tong_fte_can),
        "ty_le_sv_gv_hien_tai": float(ty_le_hien_tai),
        "tong_de_xuat_tuyen": int(tong_de_xuat),
        "ty_le_chuan": float(ty_le_chuan),
    }

    return df_master, summary


# =========================================================
# 5. EXPORT JSON
# =========================================================
def export_json(df_master, df_gv, summary):
    print("Dang xuat data.json...")

    # Bảng chính theo khoa
    ty_le_co_huu = CONSTANTS["ty_le_co_huu"]
    khoa_data = []
    for _, row in df_master.iterrows():
        # Tách đề xuất tuyển theo tỉ lệ cơ hữu (đồng bộ app.js):
        # cơ hữu = 1.0 FTE/người; đồng cơ hữu = 0.5 FTE/người (cần gấp đôi số người)
        tong_tuyen = int(row['Tong_de_xuat_tuyen'])
        fte_co_huu = tong_tuyen * ty_le_co_huu / 100
        # Dùng floor(x+0.5) để khớp Math.round của JS (làm tròn .5 lên),
        # tránh lệch do round() của Python là làm tròn ngân hàng.
        de_xuat_co_huu = math.floor(fte_co_huu + 0.5)
        de_xuat_dong_co_huu = math.floor((tong_tuyen - fte_co_huu) / 0.5 + 0.5)
        khoa_data.append({
            "don_vi": str(row['Don_vi_quan_ly']),
            "tong_so_tiet": float(row['Tong_so_tiet_thuc_te']),
            "sv_cq": float(row['Quy_mo_CQ']),
            "sv_vlvh": float(row['Quy_mo_VLVH']),
            "sv_ctlk": float(row['Quy_mo_TXTT']),
            "sv_ths": float(row['Quy_mo_ThS']),
            "sv_ts": float(row['Quy_mo_TS']),
            "sv_quy_doi": float(row['Tong_SV_quy_doi']),
            "sv_sdh_quy_doi": float(row['SV_SDH_quy_doi']),
            "fte_hien_co": float(row['Hien_co_FTE']),
            "ts_tro_len": int(row['Hien_co_TS_tro_len']),
            "nhom_1": int(row['SL_Nhom_1']),
            "nhom_2": int(row['SL_Nhom_2']),
            "nhom_4": int(row['SL_Nhom_4']),
            "nhom_5": int(row['SL_Nhom_5']),
            "tong_quy_gio": float(row['Tong_quy_gio']),
            "sl_gs": int(row['SL_GS']),
            "sl_pgs": int(row['SL_PGS']),
            "sl_ts_hv": int(row['SL_TS']),
            "sl_ths": int(row['SL_ThS']),
            "sl_dh": int(row['SL_DH']),
            "gv_can_de_day": int(row['GV_thieu_de_day']),
            "khuyen_nghi_ts": int(row['Khuyen_nghi_tuyen_TS']),
            "de_xuat_cuc_bo": int(row['De_xuat_cuc_bo']),
            "de_xuat_bu_chuan": int(row['De_xuat_bu_chuan']),
            "tong_de_xuat": int(row['Tong_de_xuat_tuyen']),
            "de_xuat_co_huu": de_xuat_co_huu,
            "de_xuat_dong_co_huu": de_xuat_dong_co_huu,
            "ty_le_sv_gv_hien_tai": float(row['Ty_le_SV_GV_hien_tai']),
            "fte_sau_tuyen": float(row['FTE_sau_tuyen']),
            "ty_le_sv_gv_sau_tuyen": float(row['Ty_le_SV_GV_sau_tuyen']),
            "canh_bao_sdh": str(row['Canh_bao_SDH']),
        })

    # Phân bố GV toàn trường theo học hàm/vị
    hoc_ham_vi_dist = df_gv['Hoc_ham_vi_label'].value_counts().to_dict()
    nhom_dist = df_gv['Nhóm'].value_counts().to_dict()

    output = {
        "summary": summary,
        "khoa_data": sorted(khoa_data, key=lambda x: x['sv_quy_doi'], reverse=True),
        "distributions": {
            "hoc_ham_vi": {str(k): int(v) for k, v in hoc_ham_vi_dist.items()},
            "nhom": {str(k): int(v) for k, v in nhom_dist.items()},
        },
        "config": {
            "fte_weights": FTE_WEIGHTS,
            "student_weights": STUDENT_WEIGHTS,
            "constants": CONSTANTS,
            "nhom_labels": {
                "1": f"GV cơ hữu (toàn thời gian, {CONSTANTS['gio_nhom_1']} tiết/năm, hệ số nhóm = 1.0)",
                "2": f"GV đồng cơ hữu (bán thời gian, {CONSTANTS['gio_nhom_2']} tiết/năm = 50% cơ hữu, hệ số nhóm = 0.5)",
                "4": f"GV kiêm nhiệm quản lý ({CONSTANTS['gio_nhom_4']} tiết/năm, hệ số nhóm = 1.0)",
                "5": "Nghiên cứu sinh toàn thời gian (hệ số nhóm = 1.0, học vị chuẩn hóa ThS = 0.75, suy ra hệ số quy đổi GV = 0.75; không tính giờ dạy)",
            }
        },
        "notes": [
            "Công thức tính: Hệ số quy đổi GV = hệ số phân nhóm × hệ số học hàm/học vị.",
            "Hệ số phân nhóm: Cơ hữu = 1,0 · Đồng cơ hữu = 0,5 · Kiêm nhiệm QL = 1,0 · NCS toàn thời gian = 1,0.",
            "Hệ số học hàm/học vị: GS/PGS/TS = 1,0 · ThS = 0,75 · ĐH/Khác = 0,5.",
            "Nghiên cứu sinh toàn thời gian được tính như cơ hữu (nhóm = 1,0), học vị chuẩn hóa về ThS (0,75), suy ra hệ số quy đổi GV = 0,75; không tính giờ dạy.",
            "Giảng viên làm việc từ xa vẫn được tính vào định biên.",
            "Giảng viên đồng cơ hữu chỉ giảng 350 tiết/năm = 50% so với cơ hữu.",
            "Giảng viên ISB được tính vào Khoa Tài năng kinh doanh.",
            "Các đơn vị hành chính (Ban Giám hiệu, Văn phòng, Phòng Chăm sóc và hỗ trợ người học) không được tính vào định biên dù có tham gia giảng dạy.",
            "Quy mô sau đại học được phân bổ về Khoa/Viện theo số chương trình đào tạo.",
            "Sinh viên Chương trình liên kết (CTLK) được quy đổi theo hệ số 0,75.",
            "Tổng chỉ tiêu tuyển được tách theo tỉ lệ cơ hữu (mặc định 70%); phần còn lại là đồng cơ hữu.",
            "Bảng dữ liệu bên dưới cho phép chỉnh sửa các cột đầu vào để mô phỏng; bấm \"Khôi phục\" để trả về số liệu gốc.",
        ]
    }

    payload = json.dumps(output, ensure_ascii=False, indent=2)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        f.write(payload)
    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write("const DATA_INIT = ")
        f.write(payload)
        f.write(";")

    print(f"Da xuat thanh cong: {os.path.basename(OUTPUT_JS)} + {os.path.basename(OUTPUT_JSON)}")
    return output


# =========================================================
# 6. MAIN
# =========================================================
def main(file_path=None):
    df_hr, df_demand, df_ug, df_pg, df_mapping, df_ctdt = extract_data(file_path)
    df_master, df_gv, danh_sach_khoa = transform_data(df_hr, df_demand, df_ug, df_pg, df_mapping, df_ctdt)
    df_result, summary = optimize_multi_stage(df_master)
    export_json(df_result, df_gv, summary)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        main(path)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"\n[LOI] {e}", file=sys.stderr)
        sys.exit(1)
