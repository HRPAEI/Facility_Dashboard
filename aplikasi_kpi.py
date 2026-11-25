import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import re

st.set_page_config(page_title="Facility Dashboard", layout="wide")

st.title("⚙️ HRM Electrcial Facility Abnormality & Maintenance Dashboard")
st.markdown("Data diperbarui secara *real-time* dari Google Spreadsheet.")
st.markdown("---")

@st.cache_data(ttl=5)
def muat_data_baru():
    tautan_resmi = "https://docs.google.com/spreadsheets/d/1AWMk2xCkLc9_AqjbZQ6DvkGnxiQSVVf9PHMuXM56j50/export?format=csv&gid=0"
    
    response = requests.get(tautan_resmi, verify=False)
    response.raise_for_status()
    
    df = pd.read_csv(io.StringIO(response.text))
    st.write(df.columns.tolist())

    df.columns = df.columns.str.strip().str.replace('\n', ' ', regex=False)
    df = df.dropna(subset=['No.'])

    df['Facility'] = (
        df['Facility']
        .astype(str)
        .str.replace(r'[\n\r\t\xa0]', ' ', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .str.upper()
    )

    df['Equipment'] = (
        df['Equipment']
        .astype(str)
        .str.replace(r'[\n\r\t\xa0]', ' ', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .str.upper()
    )
    
    def bersihkan_waktu(nilai):
        if pd.isna(nilai): return 0
        try:
            potong = str(nilai).strip().split(':')
            if len(potong) >= 2:
                return int(potong[0]) * 60 + int(potong[1])
            return 0
        except: return 0

    df['Stop_Minutes'] = df['Stop time'].apply(bersihkan_waktu)
    return df


try:
    df = muat_data_baru()

    # ── KPI Metrik ──────────────────────────────────────────────
    total_kasus = len(df)
    total_menit = df['Stop_Minutes'].sum()
    downtime_teks = f"{total_menit // 60} hour {total_menit % 60} Minutes"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Breakdown cases", f"{total_kasus} cases")
    c2.metric("Total Accumulated Downtime", downtime_teks)
    
    modus_fac = df['Facility'].mode()[0] if not df['Facility'].empty else "-"
    c3.metric("Most Frequent Problem Facility", modus_fac)

    modus_eqp = df['Equipment'].mode()[0] if not df['Equipment'].empty else "-"
    c4.metric("Most Frequent Problem Equipment", modus_eqp)

    if not df.empty:
        df_stop = df.groupby('Facility')['Stop_Minutes'].sum()
        longest_fac   = df_stop.idxmax()
        longest_menit = int(df_stop.max())
        longest_teks  = f"{longest_menit // 60}h {longest_menit % 60}m"
    else:
        longest_fac, longest_teks = "-", "-"
    c5.metric("Longest Stop Facility", longest_fac, delta=longest_teks, delta_color="inverse")

    st.markdown("---")

    # ── Visualisasi Utama ────────────────────────────────────────
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("📊 Total Downtime by Facility")
        df_fac = df.groupby('Facility')['Stop_Minutes'].sum().reset_index()
        st.plotly_chart(
            px.bar(df_fac, x='Facility', y='Stop_Minutes', color='Facility', text_auto=True),
            use_container_width=True
        )
    with g2:
        st.subheader("🏭 Cases Based on Facility")
        df_fac_count = df['Facility'].value_counts().reset_index()
        df_fac_count.columns = ['Facility', 'Total']
        st.plotly_chart(
            px.pie(df_fac_count, names='Facility', values='Total', hole=0.4),
            use_container_width=True
        )

    st.markdown("---")

    # ── Tabel Data Lengkap ───────────────────────────────────────
    st.subheader("📋 Facility Breakdowns Detail Log")
    kolom = [
    'No.', 'Date', 'Start time', 'End time', 'Stop time',
    'Facility', 'Equipment', 'Facility abnormality details',
    'Field\nwork\n action',
    'Worker', 'Shift work', 'Emergency\n call'
]

    
    df_tampil = df[kolom].copy()
    df_tampil['No.'] = df_tampil['No.'].astype(str).str.replace('.0', '', regex=False)

    st.dataframe(
        df_tampil,
        use_container_width=True,
        hide_index=True,
        column_config={
            'No.': st.column_config.TextColumn('No.', width='small'),
        }
    )

    st.markdown("---")

    # ── 📈 MULTI-LINE CHART — Trend per Facility ────────────────
    st.subheader("📈 Breakdown Trend per Facility (Over Time)")

    col_toggle1, col_toggle2 = st.columns([1, 3])
    with col_toggle1:
        granularitas = st.radio(
            "Tampilkan per:",
            options=["Daily", "Weekly", "Monthly"],
            horizontal=True
        )

    df_trend = df.copy()
    df_trend['Date'] = pd.to_datetime(df_trend['Date'], dayfirst=True, errors='coerce')
    df_trend = df_trend.dropna(subset=['Date'])

    if granularitas == "Daily":
        df_trend['Periode'] = df_trend['Date'].dt.to_period('D').dt.to_timestamp()
    elif granularitas == "Weekly":
        df_trend['Periode'] = df_trend['Date'].dt.to_period('W').dt.to_timestamp()
    else:
        df_trend['Periode'] = df_trend['Date'].dt.to_period('M').dt.to_timestamp()

    tab1, tab2 = st.tabs(["📦 Number of Cases", "⏱️ Total Downtime (Minutes)"])

    with tab1:
        df_cases = (
            df_trend.groupby(['Periode', 'Facility'])
            .size()
            .reset_index(name='Cases')
        )
        fig_cases = px.line(
            df_cases,
            x='Periode', y='Cases',
            color='Facility',
            markers=True,
            title=f"Breakdown Cases per Facility ({granularitas})",
            labels={'Periode': 'Date', 'Cases': 'Number of Cases'}
        )
        fig_cases.update_layout(
            hovermode='x unified',
            xaxis_title='Date',
            yaxis_title='Number of Cases',
            legend_title='Facility'
        )
        st.plotly_chart(fig_cases, use_container_width=True)

    with tab2:
        df_downtime = (
            df_trend.groupby(['Periode', 'Facility'])['Stop_Minutes']
            .sum()
            .reset_index()
        )
        fig_downtime = px.line(
            df_downtime,
            x='Periode', y='Stop_Minutes',
            color='Facility',
            markers=True,
            title=f"Total Downtime per Facility ({granularitas})",
            labels={'Periode': 'Date', 'Stop_Minutes': 'Downtime (Minutes)'}
        )
        fig_downtime.update_layout(
            hovermode='x unified',
            xaxis_title='Date',
            yaxis_title='Downtime (Minutes)',
            legend_title='Facility'
        )
        st.plotly_chart(fig_downtime, use_container_width=True)

    st.markdown("---")

    # ── 🔍 SEARCH BOX — Equipment Breakdown per Facility ────────
    st.subheader("🔍 Equipment Breakdown Search by Facility")

    daftar_facility = sorted(df['Facility'].dropna().unique().tolist())

    pilihan_facility = st.selectbox(
        "Pilih atau ketik nama Facility:",
        options=["-- Pilih Facility --"] + daftar_facility,
        index=0
    )

    if pilihan_facility != "-- Pilih Facility --":

        df_filtered = df[df['Facility'] == pilihan_facility]

        # ── Sub-KPI untuk facility terpilih
        total_kasus_fac   = len(df_filtered)
        total_menit_fac   = df_filtered['Stop_Minutes'].sum()
        downtime_fac_teks = f"{total_menit_fac // 60}h {total_menit_fac % 60}m"

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Cases", f"{total_kasus_fac} cases")
        k2.metric("Total Downtime", downtime_fac_teks)
        k3.metric(
            "Most Problematic Equipment",
            df_filtered['Equipment'].mode()[0] if not df_filtered.empty else "-"
        )

        st.markdown("")

        # ── Grafik Bar: Equipment vs Jumlah Kasus & Downtime
        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown(f"**📦 Cases per Equipment — {pilihan_facility}**")
            df_eqp_count = (
                df_filtered['Equipment']
                .value_counts()
                .reset_index()
            )
            df_eqp_count.columns = ['Equipment', 'Cases']
            fig_count = px.bar(
                df_eqp_count,
                x='Equipment', y='Cases',
                color='Equipment',
                text_auto=True,
                title=f"Number of Cases per Equipment ({pilihan_facility})"
            )
            fig_count.update_layout(showlegend=False, xaxis_tickangle=-30)
            st.plotly_chart(fig_count, use_container_width=True)

        with ch2:
            st.markdown(f"**⏱️ Total Downtime per Equipment — {pilihan_facility}**")
            df_eqp_down = (
                df_filtered.groupby('Equipment')['Stop_Minutes']
                .sum()
                .reset_index()
                .sort_values('Stop_Minutes', ascending=False)
            )
            fig_down = px.bar(
                df_eqp_down,
                x='Equipment', y='Stop_Minutes',
                color='Equipment',
                text_auto=True,
                title=f"Total Downtime per Equipment ({pilihan_facility})"
            )
            fig_down.update_layout(showlegend=False, xaxis_tickangle=-30)
            st.plotly_chart(fig_down, use_container_width=True)

        # ── Tabel detail untuk facility terpilih
        st.markdown(f"**📋 Detail Log — {pilihan_facility}**")
      kolom_detail = [
    'No.', 'Date', 'Start time', 'End time', 'Stop time',
    'Facility', 'Equipment', 'Facility abnormality details',
    'Field\nwork\n action', 'Worker', 'Shift work', 'Emergency\n call'
]

        df_detail = df_filtered[kolom_detail].copy()
        df_detail['No.'] = df_detail['No.'].astype(str).str.replace('.0', '', regex=False)
        st.dataframe(df_detail, use_container_width=True, hide_index=True)

    st.markdown("---")

except Exception as e:
    st.error(f"Gagal memproses data. Error: {e}")
