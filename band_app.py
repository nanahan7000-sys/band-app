import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定 ---
# JSONファイルの名前（デスクトップに置いてあるファイル名と合わせてください）
JSON_FILE = "service_account.json"
# スプレッドシートの名前（Googleスプレッドシートのタイトルと合わせてください）
SHEET_NAME = "band_app_db"

MEMBERS = ["サックス", "トロンボーン", "トランペット", "リズム"]

# --- 関数: スプレッドシートへの接続 ---
def connect_db():
    # 認証情報の範囲（読み書き権限）
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # 鍵ファイルを使って認証
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    client = gspread.authorize(creds)
    # シートを開く
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

# --- 関数: データの読み込み ---
def load_data():
    try:
        sheet = connect_db()
        # 全データを取得
        data = sheet.get_all_records()
        # データがあればDataFrameにする、なければ空の箱を作る
        if data:
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame(columns=["日付", "名前", "曲名", "練習箇所", "時間(分)", "進捗(%)", "コメント"])
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return pd.DataFrame(columns=["日付", "名前", "曲名", "練習箇所", "時間(分)", "進捗(%)", "コメント"])

# --- 関数: データの追加 ---
def add_data(new_row_df):
    try:
        sheet = connect_db()
        # DataFrameの1行目をリストに変換して追加
        row_list = new_row_df.iloc[0].tolist()
        # 日付などを文字列に変換（エラー防止）
        row_list = [str(item) for item in row_list]
        sheet.append_row(row_list)
    except Exception as e:
        st.error(f"データ保存エラー: {e}")

# --- 関数: データの削除（行ごと消す） ---
def delete_data(row_index):
    try:
        sheet = connect_db()
        # スプレッドシートは1行目がタイトルなので、行番号は +2 される（Pythonは0始まり、Sheetは1始まり＋タイトル分）
        sheet.delete_rows(row_index + 2)
    except Exception as e:
        st.error(f"削除エラー: {e}")

# --- メインアプリ ---
def main():
    st.set_page_config(page_title="チャリオパート別練習状況", layout="wide")
    st.title("🎷 チャリオパート別練習状況 (Cloud版)")

    # データのロード
    df = load_data()

    # タブ設定
    tab1, tab2, tab3 = st.tabs(["📝 練習報告", "📊 現在の状況", "🗑️ 履歴の修正"])

    # --- タブ1: 練習報告フォーム ---
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
            
            comment = st.text_area(
                "メモ・共有事項",
                placeholder="BPM120で合わせました、ここが難しかったです、等"
            )
            
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
                    # スプレッドシートに追加
                    add_data(new_data)
                    st.success(f"スプレッドシートに保存しました！ ({song} - {section})")
                    # 画面を更新して反映させる（少し待つ必要があるためsleepは使わずrerun）
                    st.rerun()

    # --- タブ2: ダッシュボード ---
    with tab2:
        st.header("みんなの練習状況")
        if not df.empty:
            st.subheader("📢 直近の活動ログ")
            st.dataframe(
                df.sort_values("日付", ascending=False).head(10),
                use_container_width=True
            )
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🔥 パート別 累積練習時間")
                # 数値型になっていない場合の対策
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

    # --- タブ3: 履歴の修正（削除機能） ---
    with tab3:
        st.header("データの削除")
        st.write("間違えて登録したデータを選択して削除できます（スプレッドシートから直接消します）。")
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            # 削除用のインデックス選択
            delete_index = st.selectbox("削除したいデータの番号（一番左の数字）を選んでください", df.index)
            
            if not df.empty and delete_index in df.index:
                target_row = df.loc[delete_index]
                st.warning(f"以下のデータを削除しますか？\n\n日付: {target_row['日付']} | 名前: {target_row['名前']} | 曲名: {target_row['曲名']}")
                
                if st.button("削除を実行する", type="primary"):
                    # スプレッドシートから削除
                    delete_data(delete_index)
                    st.success("削除しました！")
                    st.rerun()
        else:
            st.info("削除できるデータがありません。")

if __name__ == "__main__":
    main()