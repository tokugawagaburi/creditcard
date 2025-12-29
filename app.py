import streamlit as st
import pandas as pd
import os
import re

# --- 1. 定義 ---
CATEGORIES = ["未分類", "旅費・交通費", "燃料費", "福利厚生費", "通信費", "材料費", "消耗品", "会費", "書籍", "交際費", "修繕費", "その他"]
RULES_FILE = "classification_rules.csv"

# --- 関数群 ---
def load_rules():
    if os.path.exists(RULES_FILE): return pd.read_csv(RULES_FILE)
    return pd.DataFrame(columns=["keyword", "category"])

def save_rules_to_file(df):
    df.to_csv(RULES_FILE, index=False, encoding="utf_8_sig")

def auto_classify(name, rules_df):
    name_str = str(name).upper()
    for _, row in rules_df.iterrows():
        if str(row["keyword"]).upper() in name_str: return row["category"]
    return "未分類"

def clean_to_int(value):
    if pd.isna(value) or value == "": return 0
    s_val = str(value).split('.')[0]
    cleaned = re.sub(r'[^-0-9]', '', s_val)
    try: return int(cleaned)
    except: return 0

def highlight_unclassified_rows(row):
    return ['background-color: #ffcccc' if row['カテゴリー'] == '未分類' else ''] * len(row)

# --- ★印刷用CSS（画面上では何も隠さず、印刷時のみ適用） ---
st.markdown("""
    <style>
    @media print {
        /* 印刷時に隠すもの：サイドバー、ボタン類、アップローダー、グラフ、注意書き */
        [data-testid="stSidebar"], 
        .stButton, 
        [data-testid="stFileUploader"],
        [data-testid="stArrowVegaLiteChart"],
        .stAlert,
        header,
        footer {
            display: none !important;
        }
        /* 明細編集テーブルも印刷時は隠す（小計表だけ残す） */
        [data-testid="stDataEditor"] {
            display: none !important;
        }
        /* 印刷の余白調整 */
        .main .block-container {
            padding: 0 !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="経費精算くん", layout="wide", page_icon="💴")
st.title("💴 経費仕分け・集計システム")

# --- 2. サイドバー：ルール管理（復活） ---
st.sidebar.header("⚙️ 設定と学習")
current_rules = load_rules()

with st.sidebar.expander("➕ 新しいルールを追加"):
    with st.form("add_rule_form", clear_on_submit=True):
        kw = st.text_input("店名のキーワード")
        cat = st.selectbox("勘定科目", CATEGORIES)
        if st.form_submit_button("マスタに登録"):
            if kw:
                rules = load_rules()
                rules = pd.concat([rules[rules["keyword"] != kw], pd.DataFrame({"keyword": [kw], "category": [cat]})], ignore_index=True)
                save_rules_to_file(rules)
                st.sidebar.success(f"「{kw}」を登録")

st.sidebar.divider()
if st.sidebar.button("🎯 ルールを未分類に一括適用", type="primary", use_container_width=True):
    if "df" in st.session_state:
        rules = load_rules()
        mask = st.session_state.df["カテゴリー"] == "未分類"
        st.session_state.df.loc[mask, "カテゴリー"] = st.session_state.df.loc[mask, st.session_state.name_col].apply(lambda x: auto_classify(x, rules))
        st.rerun()

if not current_rules.empty:
    st.sidebar.subheader("📋 登録済みリスト")
    edited_rules = st.sidebar.data_editor(current_rules, num_rows="dynamic", hide_index=True, key="rules_editor")
    if st.sidebar.button("マスタの変更を保存"):
        save_rules_to_file(edited_rules)
        st.sidebar.info("保存完了。反映は一括適用ボタンで。")

# --- 3. メイン処理：CSV読み込み ---
uploaded_file = st.file_uploader("CSVをアップロードしてください", type="csv")

if uploaded_file:
    if "df" not in st.session_state or st.session_state.get("file_name") != uploaded_file.name:
        for enc in ['cp932', 'shift_jis', 'utf-8']:
            try:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file, encoding=enc)
                break
            except: continue
        
        if df_raw is not None:
            n_col, a_col = df_raw.columns[0], df_raw.columns[min(1, len(df_raw.columns)-1)]
            for c in df_raw.columns:
                if any(k in c for k in ["店名", "内容", "摘要"]): n_col = c
                if "金額" in c: a_col = c
            
            st.session_state.file_name = uploaded_file.name
            st.session_state.name_col = n_col
            df_raw["金額"] = df_raw[a_col].apply(clean_to_int)
            df_raw["カテゴリー"] = df_raw[n_col].apply(lambda x: auto_classify(x, load_rules()))
            other_cols = [c for c in df_raw.columns if c not in ["カテゴリー", "金額"]]
            st.session_state.df = df_raw[["カテゴリー", "金額"] + other_cols]

# データの表示・編集
if "df" in st.session_state:
    # メインの合計金額（赤色表示を維持）
    total_val = st.session_state.df["金額"].sum()
    st.markdown(f"## 現在の合計: <span style='color:#ff4b4b; font-size:40px;'>¥{int(total_val):,}</span>", unsafe_allow_html=True)

    st.subheader("📝 明細編集")
    updated_data = st.data_editor(
        st.session_state.df.style.apply(highlight_unclassified_rows, axis=1), 
        column_config={
            "カテゴリー": st.column_config.SelectboxColumn("勘定科目", options=CATEGORIES, required=True),
            "金額": st.column_config.NumberColumn("金額", format="¥%d")
        },
        disabled=[c for c in st.session_state.df.columns if c != "カテゴリー"],
        hide_index=True, use_container_width=True, key="main_editor"
    )
    
    if st.button("✅ 編集内容を確定して集計を更新", type="primary", use_container_width=True):
        st.session_state.df = pd.DataFrame(updated_data)
        st.rerun()

    # --- 4. 集計・報告セクション ---
    st.divider()
    st.header("📊 経費集計サマリー")
    
    summary = st.session_state.df.groupby("カテゴリー")["金額"].sum().reindex(CATEGORIES).fillna(0).reset_index()
    summary_display = summary[summary["金額"] != 0].copy()

    col1, col2 = st.columns(2)
    with col1:
        if not summary_display.empty:
            # 整数化・カンマ区切り
            summary_display["金額（円）"] = summary_display["金額"].apply(lambda x: f"¥{int(x):,}")
            st.dataframe(
                summary_display[["カテゴリー", "金額（円）"]].style.apply(highlight_unclassified_rows, axis=1),
                hide_index=True, use_container_width=True
            )
        
        # 未分類警告
        un_val = summary.loc[summary["カテゴリー"] == "未分類", "金額"].sum()
        if un_val > 0:
            st.warning(f"⚠️ 未分類残額: ¥{int(un_val):,}")
        else:
            st.success("✅ 全項目仕分け済み")

    with col2:
        if not summary_display.empty:
            st.bar_chart(summary_display.set_index("カテゴリー")["金額"])

    st.info("💡 印刷したい時は Ctrl+P を押してください。サマリー表と合計金額のみが抽出されます。")
    st.download_button("✅ CSVを保存", st.session_state.df.to_csv(index=False).encode('utf_8_sig'), f"result_{st.session_state.file_name}")