import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- 設定 ---
JSON_FILE = "service_account.json"
SHEET_NAME = "band_app_db"
MEMBERS = ["サックス", "トロンボーン", "トランペット", "リズム"]

# --- 関数: スプレッドシートへの接続 ---
def connect_db():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 【ここが変更点】クラウド上の「秘密の鍵」があるか確認
    if "gcp_json" in st.secrets:
        # あれば、それを使う（Cloud用）
        key_dict = json.loads(st.secrets["gcp_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    else:
        # なければ、手元のファイルを使う（Local用）
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# --- 関数: データの読み込み ---
def load_data():
    try:
        sheet = connect_db()
        data = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame(columns=["日付", "名前", "曲名", "練習箇所", "時間(分)", "進捗(%)", "コメント"])
        return df
    except Exception as e:
        # エラーが出てもアプリが止まらないように空のデータを返す
        st.error(f"データ読み込みエラー: {e}")
        return pd.DataFrame(columns=["日付", "名前", "曲名", "練習箇所", "時間(分)", "進捗(%)", "コメント"])

# --- 関数: データの追加 ---
def add_data(new_row_df):
    try:
        sheet = connect_db()
        row_list = new_row_df.iloc[0].tolist()
        row_list = [str(item) for item in row_list]
        sheet.append_row(row_list)
    except Exception as e:
        st.error(f"データ保存エラー: {e}")

# --- 関数: データの削除 ---
def delete_data(row_index):
    try:
        sheet = connect_db()
        sheet.delete_rows(row_index + 2)
    except Exception as e:
        st.error(f"削除エラー: {e}")

# --- メインアプリ ---
def main():
    st.set_page_config(page_title="チャリオパート別練習状況", layout="wide")
    st.title("🎷 チャリオパート別練習状況")

    df = load_data()

    tab1, tab2, tab3 = st.tabs(["📝 練習報告", "📊 現在の状況", "🗑️ 履歴の修正"])

    with tab1:
        st.header("今日の練習を報告")
        with st.form("report_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.selectbox("パート（名前）", MEMBERS)
                date = st.date_input("日付", datetime.today())
                section = st.text_input("練習した箇所", placeholder="例: A, サビ, イントロ, 通し")
            with col2:
                song = st.text_input("練習した曲名", placeholder="例: 新曲A, 基礎練習")
                duration = st.number_input("練習時間（分）", min_value=0, step=10, value=30)
            
            progress = st.slider("この曲の仕上がり具合（%）", 0, 100, 50)
            comment = st.text_area("メモ・共有事項", placeholder="BPM120で合わせました、等")
            
            submitted = st.form_submit_button("送信する")
            
            if submitted:
                if not song:
                    st.error("曲名を入力してください！")
                elif not section:
                    st.error("練習した箇所を入力してください！")
                else:
                    new_data = pd.DataFrame({
                        "日付": [date],
                        "名前": [name],
                        "曲名": [song],
                        "練習箇所": [section],
                        "時間(分)": [duration],
                        "進捗(%)": [progress],
                        "コメント": [comment]
                    })
                    add_data(new_data)
                    st.success(f"保存しました！ ({song} - {section})")
                    st.rerun()

    with tab2:
        st.header("みんなの練習状況")
        if not df.empty:
            st.subheader("📢 直近の活動ログ")
            st.dataframe(df.sort_values("日付", ascending=False).head(10), use_container_width=True)
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🔥 パート別 累積練習時間")
                df["時間(分)"] = pd.to_numeric(df["時間(分)"], errors='coerce').fillna(0)
                total_time = df.groupby("名前")["時間(分)"].sum().reset_index()
                st.bar_chart(total_time, x="名前", y="時間(分)")
            with col_b:
                st.subheader("🎶 曲の仕上がり進捗 (最新)")
                df["進捗(%)"] = pd.to_numeric(df["進捗(%)"], errors='coerce').fillna(0)
                latest_progress = df.sort_values("日付").groupby(["曲名", "名前"]).last().reset_index()
                avg_progress = latest_progress.groupby("曲名")["進捗(%)"].mean()
                st.bar_chart(avg_progress)
            
            with st.expander("💬 最新のコメントを確認"):
                for index, row in df.sort_values("日付", ascending=False).head(5).iterrows():
                    st.markdown(f"**{row['名前']}** | {row['曲名']} (**{row['練習箇所']}**)\n\n{row['コメント']}")
                    st.divider()
        else:
            st.info("まだデータがありません。")

    with tab3:
        st.header("データの削除")
        if not df.empty:
            st.