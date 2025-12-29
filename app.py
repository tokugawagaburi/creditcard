import streamlit as st
import pandas as pd
import json
import re
import unicodedata
from streamlit_local_storage import LocalStorage

# --- 1. 基本設定 ---
ls = LocalStorage()
DEFAULT_CATEGORIES = ["🔴 未分類", "旅費・交通費", "燃料費", "福利厚生費", "通信費", "材料費", "消耗品", "会費", "書籍", "交際費", "修繕費", "その他"]

st.set_page_config(page_title="【無料・登録不要・安全】クレジットカード明細を自動仕分けする「クレカ明細仕分けくん」｜確定申告を爆速に", layout="wide", page_icon="💴")

def load_browser_data(key, default):
    raw = ls.getItem(key)
    if raw:
        try: return json.loads(raw)
        except: return default
    return default

def save_browser_data(key, data):
    ls.setItem(key, json.dumps(data))

# --- 2. 賢い仕分けロジック ---
def auto_classify(name, rules):
    if pd.isna(name): return "🔴 未分類"
    name_norm = unicodedata.normalize('NFKC', str(name)).upper().strip()
    for rule in rules:
        rule_kw = unicodedata.normalize('NFKC', str(rule["keyword"])).upper().strip()
        if rule_kw in name_norm:
            return rule["category"]
    return "🔴 未分類"

def clean_to_int(value):
    if pd.isna(value) or value == "": return 0
    s_val = str(value).split('.')[0]
    cleaned = re.sub(r'[^-0-9]', '', s_val)
    try: return int(cleaned)
    except: return 0

# セッション状態の初期化
if "categories" not in st.session_state:
    st.session_state.categories = load_browser_data("my_expense_categories", DEFAULT_CATEGORIES)
if "rules" not in st.session_state:
    st.session_state.rules = load_browser_data("my_expense_rules", [])

# --- 3. サイドバー：学習・設定 ---
st.sidebar.title("⚙️ 設定・学習")

# ① 新しいルールを教える
with st.sidebar.expander("🎓 新しいルールを教える", expanded=True):
    with st.form("rule_form"):
        kw = st.text_input("キーワード (例: ETC)")
        # 未分類以外から選択させる
        usable_cats = [c for c in st.session_state.categories if "未分類" not in c]
        cat = st.selectbox("分類するカテゴリー", usable_cats)
        if st.form_submit_button("このルールを学習する"):
            if kw:
                new_rules = [r for r in st.session_state.rules if r["keyword"] != kw]
                new_rules.append({"keyword": kw, "category": cat})
                st.session_state.rules = new_rules
                save_browser_data("my_expense_rules", new_rules)
                if "df" in st.session_state:
                    st.session_state.df["カテゴリー"] = st.session_state.df["内容"].apply(lambda x: auto_classify(x, st.session_state.rules))
                st.success(f"「{kw}」を学習しました！")
                st.rerun()

# ② 学習したルールの管理
with st.sidebar.expander("📝 学習したルールの編集・消去"):
    if st.session_state.rules:
        edited_rules = st.data_editor(
            st.session_state.rules, 
            num_rows="dynamic", 
            hide_index=True,
            column_config={
                "category": st.column_config.SelectboxColumn("カテゴリー", options=st.session_state.categories)
            }
        )
        if st.sidebar.button("ルールの変更を保存", width='stretch'):
            st.session_state.rules = edited_rules
            save_browser_data("my_expense_rules", edited_rules)
            if "df" in st.session_state:
                st.session_state.df["カテゴリー"] = st.session_state.df["内容"].apply(lambda x: auto_classify(x, st.session_state.rules))
            st.rerun()

# ③ カテゴリー自体の編集
with st.sidebar.expander("📁 カテゴリー名の追加・編集"):
    st.write("※「🔴 未分類」は削除できません")
    cat_text = st.text_area("一行に一つ入力", value="\n".join(st.session_state.categories))
    if st.sidebar.button("カテゴリー一覧を更新", width='stretch'):
        new_cats = [c.strip() for c in cat_text.split("\n") if c.strip()]
        if "🔴 未分類" not in new_cats:
            new_cats.insert(0, "🔴 未分類") # 未分類を強制的に先頭へ
        
        st.session_state.categories = new_cats
        save_browser_data("my_expense_categories", new_cats)
        st.success("カテゴリーを更新しました！")
        st.rerun()

st.sidebar.divider()
st.sidebar.subheader("🥤 開発者を応援する")
st.sidebar.caption("「今年の確定申告が楽になった！」「応援したい」という方は、こちらからコーヒー一杯分のギフトをいただけると、研究と開発の励みになります！")

ofuse_url = "https://ofuse.me/0cb597b9" 
st.sidebar.markdown(f"[:link: **OFUSEで応援メッセージを送る**]({ofuse_url})")

if st.sidebar.button("🧹 全データを初期化", width='stretch'):
    st.session_state.clear()
    st.rerun()

# --- 4. メイン画面：解析 ---
st.title("💴 【無料・登録不要・安全】クレジットカード明細を自動仕分けする「クレカ明細仕分けくん」｜確定申告を爆速に")

uploaded_files = st.file_uploader("CSVファイルを選択", type="csv", accept_multiple_files=True)

if uploaded_files:
    if st.session_state.get("file_ids") != [f.name for f in uploaded_files]:
        st.session_state.file_ids = [f.name for f in uploaded_files]
        all_dfs = []
        for f in uploaded_files:
            for enc in ['cp932', 'shift_jis', 'utf-8']:
                try:
                    f.seek(0)
                    df_tmp = pd.read_csv(f, encoding=enc)
                    df_tmp["元ファイル"] = f.name
                    all_dfs.append(df_tmp)
                    break
                except: continue
        if all_dfs:
            st.session_state.raw_df = pd.concat(all_dfs, ignore_index=True)

    if "raw_df" in st.session_state and "df" not in st.session_state:
        col_a, col_b = st.columns(2)
        name_col = col_a.selectbox("店名・内容の列", st.session_state.raw_df.columns)
        price_col = col_b.selectbox("金額の列", st.session_state.raw_df.columns)
        if st.button("🚀 解析を開始する", type="primary", width='stretch'):
            df = st.session_state.raw_df.copy()
            df["内容"] = df[name_col]
            df["金額"] = df[price_col].apply(clean_to_int)
            df["カテゴリー"] = df["内容"].apply(lambda x: auto_classify(x, st.session_state.rules))
            main_cols = ["カテゴリー", "内容", "金額", "元ファイル"]
            st.session_state.df = df[main_cols + [c for c in df.columns if c not in main_cols]]
            st.rerun()

# --- 5. 編集・集計 ---
if "df" in st.session_state:
    st.divider()
    unclassified_df = st.session_state.df[st.session_state.df["カテゴリー"].str.contains("未分類", na=False)]
    if not unclassified_df.empty:
        st.warning(f"⚠️ まだ {len(unclassified_df)} 件（¥{int(unclassified_df['金額'].sum()):,}）の未分類があります。")

    updated_df = st.data_editor(
        st.session_state.df.style.apply(lambda r: ['background-color: #FFD1D1' if "未分類" in str(r.カテゴリー) else ''] * len(r), axis=1),
        column_config={
            "カテゴリー": st.column_config.SelectboxColumn("📁 勘定科目", options=st.session_state.categories, required=True),
            "内容": st.column_config.TextColumn("🏷️ 内容", disabled=True),
            "金額": st.column_config.NumberColumn("💰 金額", format="¥%d", disabled=True)
        },
        width='stretch', hide_index=True, key="main_editor"
    )
    
    if st.button("✅ 編集を保存", type="primary", width='stretch'):
        st.session_state.df = updated_df
        st.rerun()

    # 集計とダウンロード
    summary = st.session_state.df.groupby("カテゴリー")["金額"].sum().reset_index()
    summary_display = summary[summary["金額"] > 0]
    if not summary_display.empty:
        st.subheader("📊 科目別集計")
        col_l, col_r = st.columns([1, 1])
        col_l.dataframe(summary_display, hide_index=True, width='stretch')
        col_r.bar_chart(summary_display.set_index("カテゴリー")["金額"])

    def create_report(df, categories):
        summ = df.groupby("カテゴリー")["金額"].sum().reset_index()
        summ = summ[summ["金額"] > 0]
        rep = "【クレカ明細仕分け結果】\n\n■ 集計表\nカテゴリー,金額\n"
        for _, r in summ.iterrows(): rep += f"{r['カテゴリー']},{int(r['金額'])}\n"
        rep += f"総合計,{int(df['金額'].sum())}\n\n■ 明細一覧\n" + df.to_csv(index=False)
        return rep

    st.download_button("📥 結果を保存", create_report(st.session_state.df, st.session_state.categories).encode('utf_8_sig'), 
                       file_name=f"クレカ明細仕分け結果.csv", mime="text/csv", width='stretch')




