import streamlit as st
from openai import OpenAI
import os
import json
import hashlib
import re
import random
from datetime import date, datetime
from pathlib import Path

# ──────────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="くまっち占い",
    page_icon="🔮",
    layout="centered"
)

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0d0d2b 0%, #1a0533 50%, #0d0d2b 100%);
    }
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        color: #e8c97e;
        text-shadow: 0 0 20px #e8c97e88;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        text-align: center;
        color: #b08fd4;
        font-size: 1rem;
        margin-bottom: 2rem;
        letter-spacing: 0.2em;
    }
    .fortune-card {
        background: linear-gradient(145deg, #1c0a3a, #2d1060);
        border: 1px solid #6a3d9a55;
        border-radius: 16px;
        padding: 1.8rem 2rem;
        color: #e8dff5;
        font-size: 1.05rem;
        line-height: 2.0;
        box-shadow: 0 0 30px #6a3d9a44;
        margin-top: 1rem;
        white-space: pre-wrap;
    }
    .song-card {
        background: linear-gradient(145deg, #1c0a3a, #2d1060);
        border: 1px solid #e8c97e55;
        border-radius: 14px;
        padding: 1.2rem 1.6rem;
        color: #e8dff5;
        font-size: 1.0rem;
        line-height: 1.7;
        box-shadow: 0 0 20px #e8c97e33;
        margin-top: 0.9rem;
    }
    .song-title {
        color: #e8c97e;
        font-size: 1.15rem;
        font-weight: bold;
    }
    .song-meta {
        color: #b08fd4;
        font-size: 0.9rem;
        margin-bottom: 0.3rem;
    }
    .song-reason {
        color: #e8dff5;
        font-size: 0.92rem;
        margin-top: 0.3rem;
    }
    .stSelectbox label, .stTextInput label {
        color: #c9a9e8 !important;
        font-size: 0.95rem !important;
    }
    .stButton button {
        background: linear-gradient(135deg, #6a3d9a, #9b59b6);
        color: white;
        border: none;
        border-radius: 50px;
        padding: 0.6rem 2.5rem;
        font-size: 1.1rem;
        font-weight: bold;
        width: 100%;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 15px #6a3d9a66;
    }
    .stButton button:hover {
        box-shadow: 0 6px 25px #9b59b688;
        transform: translateY(-2px);
    }
    .cache-badge {
        display: inline-block;
        background: #2d1060;
        color: #b08fd4;
        border: 1px solid #6a3d9a55;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.8rem;
        margin-top: 0.5rem;
    }
    .fortune-id-box {
        background: #110826;
        border: 1px solid #6a3d9a33;
        border-radius: 10px;
        padding: 0.7rem 1.2rem;
        color: #b08fd4;
        font-size: 0.9rem;
        margin-top: 0.8rem;
    }
    .fortune-id-value {
        font-family: monospace;
        color: #e8c97e;
        font-size: 1.1rem;
        letter-spacing: 0.15em;
    }
    .section-divider {
        border: none;
        border-top: 1px solid #6a3d9a44;
        margin: 1.2rem 0;
    }
    .stRadio label {
        color: #c9a9e8 !important;
    }
    .stRadio > div {
        flex-direction: row !important;
        gap: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────
CACHE_FILE = Path(__file__).parent / "fortune_cache.json"
OPENAI_MODEL = "gpt-5-mini"
OPENAI_FALLBACK_MODEL = "gpt-4o-mini"

LUCKY_COLORS = ["赤", "青", "黄", "緑", "紫", "ピンク", "白", "黒", "ゴールド", "シルバー"]
LUCKY_ITEMS = [
    "腕時計", "ハンカチ", "手帳", "財布", "ペン", "鏡",
    "香水", "イヤリング", "マフラー", "帽子", "本", "花",
    "キャンドル", "クリスタル", "お守り", "傘", "指輪", "ブレスレット",
]

# 「開運カラオケ曲」はGPTではなく、下記の曲データベースから
# プログラム側でランダム抽選する（③毎回違う曲が出る仕様のため）。
# そのため、GPTへの指示からは曲選定の項目を除外している。
TODAY_SYSTEM_PROMPT = """\
あなたは占い師「くまっち」です。
運勢の数値はすでに決定されています。あなたの役割は「各運勢の解説」「開運アドバイス」のみです。

ユーザーから渡される運勢データをそのまま使い、必ず以下のフォーマットだけで返してください。余分な前置きは不要です。

🌟総合運
{overall_stars}
[総合運の解説を40〜60文字で。占い師らしい前向きな文章]

💕恋愛運
{love_stars}
[恋愛運の解説を40〜60文字で]

💰金運
{money_stars}
[金運の解説を40〜60文字で]

💼仕事運
{work_stars}
[仕事運の解説を40〜60文字で]

🍀健康運
{health_stars}
[健康運の解説を40〜60文字で]

🎨ラッキーカラー
{color}

🔢ラッキーナンバー
{number}

🎁ラッキーアイテム
{item}

✨開運アドバイス
[60〜100文字の具体的なアドバイス]

運勢は行動次第で変わります✨

【絶対ルール】
- 星の数は絶対に変更禁止。渡された値をそのまま正確に表示すること
- ラッキーカラー・ナンバー・アイテムも絶対に変更禁止
- 各解説は具体的で前向きな内容にする
- 占いは娯楽として提供する
- フォーマット以外の文章を追加しない\
"""

COMPAT_SYSTEM_PROMPT = """\
あなたは占い師「くまっち」です。2人の相性を占い、必ず以下のフォーマットだけで返してください。余分な説明や前置きは不要です。

💑相性スコア
{compat_stars}（{compat_score}点）

🌟総合相性
[60〜80文字で2人の総合的な相性]

💕恋愛面
[60〜80文字で恋愛における相性]

💼協力・仕事面
[60〜80文字で協力関係における相性]

🎁共通ラッキーアイテム
{item}

✨開運アドバイス
[2人へのアドバイスを60〜100文字で]

運勢は行動次第で変わります✨

【絶対ルール】
- 星とスコアは絶対に変更禁止。渡された値をそのまま使うこと
- ラッキーアイテムも絶対に変更禁止
- 占いは娯楽として提供する
- フォーマット以外の文章を追加しない\
"""

# ──────────────────────────────────────────────
# 🎤 開運カラオケ曲データベース
# ──────────────────────────────────────────────
# 構造: ERA_KEY -> [ {title, artist, year, genre, tags}, ... ]
# tags は「恋愛運UP(love)」「仕事運UP(work)」「金運UP(money)」に該当する曲だけ
# 付与する。tagsが空でも「総合運UP(overall)」では常に候補になる。
# 曲を追加したい場合は、該当する年代のリストに辞書を1つ追記するだけでよい。

SONG_DATABASE = {
    # 18〜24歳向け（2020〜2025年頃の曲を中心に）
    "current": [
        {"title": "アイドル", "artist": "YOASOBI", "year": 2023, "genre": "アニメ/J-POP", "tags": ["overall", "work"]},
        {"title": "Bling-Bang-Bang-Born", "artist": "Creepy Nuts", "year": 2024, "genre": "アニメ/ヒップホップ", "tags": ["overall", "money"]},
        {"title": "うっせぇわ", "artist": "Ado", "year": 2020, "genre": "J-POP", "tags": ["work"]},
        {"title": "ダーリン", "artist": "Mrs. GREEN APPLE", "year": 2024, "genre": "J-POP/バンド", "tags": ["love"]},
        {"title": "白日", "artist": "King Gnu", "year": 2019, "genre": "ロック", "tags": ["overall"]},
        {"title": "Subtitle", "artist": "Official髭男dism", "year": 2022, "genre": "J-POP/バンド", "tags": ["love"]},
        {"title": "NIGHT DANCER", "artist": "imase", "year": 2022, "genre": "J-POP", "tags": ["overall"]},
        {"title": "死ぬのがいいわ", "artist": "藤井風", "year": 2020, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "マリーゴールド", "artist": "あいみょん", "year": 2018, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "怪獣の花唄", "artist": "Vaundy", "year": 2020, "genre": "J-POP", "tags": ["work"]},
        {"title": "ただ君に晴れ", "artist": "ヨルシカ", "year": 2019, "genre": "バンド/ボカロ系", "tags": ["overall"]},
        {"title": "Grandeur", "artist": "Snow Man", "year": 2023, "genre": "男性アイドル", "tags": ["work", "money"]},
        {"title": "シンデレラガール", "artist": "なにわ男子", "year": 2021, "genre": "男性アイドル", "tags": ["love"]},
        {"title": "チャンスは平等", "artist": "乃木坂46", "year": 2020, "genre": "女性アイドル", "tags": ["work"]},
        {"title": "Nobody's fault", "artist": "櫻坂46", "year": 2021, "genre": "女性アイドル", "tags": ["work", "money"]},
        {"title": "Mela!", "artist": "緑黄色社会", "year": 2022, "genre": "バンド", "tags": ["overall"]},
        {"title": "Super Shy", "artist": "NewJeans", "year": 2023, "genre": "K-POP", "tags": ["love"]},
        {"title": "UNFORGIVEN", "artist": "LE SSERAFIM", "year": 2023, "genre": "K-POP", "tags": ["money", "work"]},
        {"title": "紅蓮華", "artist": "LiSA", "year": 2019, "genre": "アニメ", "tags": ["work", "money"]},
        {"title": "残響散歌", "artist": "Aimer", "year": 2021, "genre": "アニメ", "tags": ["overall"]},
    ],
    # 25〜34歳向け（2015〜2025年頃）
    "era_2015_2025": [
        {"title": "Lemon", "artist": "米津玄師", "year": 2018, "genre": "J-POPバラード", "tags": ["overall"]},
        {"title": "前前前世", "artist": "RADWIMPS", "year": 2016, "genre": "アニメ/ロック", "tags": ["love", "work"]},
        {"title": "恋", "artist": "星野源", "year": 2016, "genre": "J-POP", "tags": ["love"]},
        {"title": "Pretender", "artist": "Official髭男dism", "year": 2019, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "U.S.A.", "artist": "DA PUMP", "year": 2018, "genre": "J-POP", "tags": ["overall"]},
        {"title": "パプリカ", "artist": "Foorin", "year": 2018, "genre": "J-POP", "tags": ["overall"]},
        {"title": "夜に駆ける", "artist": "YOASOBI", "year": 2019, "genre": "J-POP", "tags": ["overall"]},
        {"title": "感電", "artist": "米津玄師", "year": 2020, "genre": "J-POP", "tags": ["work", "money"]},
        {"title": "恋するフォーチュンクッキー", "artist": "AKB48", "year": 2013, "genre": "女性アイドル", "tags": ["love", "overall"]},
        {"title": "サイレントマジョリティー", "artist": "欅坂46", "year": 2016, "genre": "女性アイドル", "tags": ["work"]},
        {"title": "君の名は希望", "artist": "乃木坂46", "year": 2016, "genre": "女性アイドル", "tags": ["work"]},
        {"title": "R.Y.U.S.E.I.", "artist": "三代目 J Soul Brothers", "year": 2014, "genre": "J-POP/ダンス", "tags": ["money", "work"]},
        {"title": "夜行", "artist": "さユり", "year": 2018, "genre": "アニメ/バラード", "tags": ["overall"]},
        {"title": "Dynamite", "artist": "BTS", "year": 2020, "genre": "K-POP", "tags": ["overall", "money"]},
        {"title": "マリーゴールド", "artist": "あいみょん", "year": 2018, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "白日", "artist": "King Gnu", "year": 2019, "genre": "ロック", "tags": ["overall"]},
        {"title": "Mela!", "artist": "緑黄色社会", "year": 2022, "genre": "バンド", "tags": ["overall"]},
        {"title": "ひまわりの約束", "artist": "秦基博", "year": 2013, "genre": "アニメバラード", "tags": ["love"]},
    ],
    # 35〜44歳向け（2005〜2015年頃）
    "era_2005_2015": [
        {"title": "桜", "artist": "コブクロ", "year": 2005, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "蕾", "artist": "コブクロ", "year": 2005, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "HANABI", "artist": "Mr.Children", "year": 2008, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "キセキ", "artist": "GReeeeN", "year": 2008, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "しるし", "artist": "Mr.Children", "year": 2007, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "ヘビーローテーション", "artist": "AKB48", "year": 2010, "genre": "女性アイドル", "tags": ["overall"]},
        {"title": "Ti Amo", "artist": "EXILE", "year": 2009, "genre": "J-POP/ダンス", "tags": ["love"]},
        {"title": "ありがとう", "artist": "いきものがかり", "year": 2010, "genre": "J-POPバラード", "tags": ["overall"]},
        {"title": "恋音と雨空", "artist": "AAA", "year": 2010, "genre": "J-POP", "tags": ["love"]},
        {"title": "Love so sweet", "artist": "嵐", "year": 2007, "genre": "男性アイドル", "tags": ["love"]},
        {"title": "Real Face", "artist": "KAT-TUN", "year": 2005, "genre": "男性アイドル", "tags": ["work", "money"]},
        {"title": "CHE.R.RY", "artist": "YUI", "year": 2006, "genre": "J-POP", "tags": ["love"]},
        {"title": "I believe", "artist": "絢香", "year": 2006, "genre": "J-POPバラード", "tags": ["work"]},
        {"title": "全力少年", "artist": "スキマスイッチ", "year": 2004, "genre": "J-POP", "tags": ["work"]},
        {"title": "さくら", "artist": "ケツメイシ", "year": 2005, "genre": "J-POP/ヒップホップ", "tags": ["love"]},
        {"title": "チョコレイト・ディスコ", "artist": "Perfume", "year": 2008, "genre": "テクノポップ", "tags": ["overall"]},
        {"title": "ひまわりの約束", "artist": "秦基博", "year": 2013, "genre": "アニメバラード", "tags": ["love"]},
        {"title": "R.Y.U.S.E.I.", "artist": "三代目 J Soul Brothers", "year": 2014, "genre": "J-POP/ダンス", "tags": ["money", "work"]},
    ],
    # 45〜54歳向け（1995〜2005年頃）
    "era_1995_2005": [
        {"title": "世界に一つだけの花", "artist": "SMAP", "year": 2003, "genre": "男性アイドル", "tags": ["work", "overall"]},
        {"title": "First Love", "artist": "宇多田ヒカル", "year": 1999, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "HOWEVER", "artist": "GLAY", "year": 1997, "genre": "ロック/バラード", "tags": ["love"]},
        {"title": "誘惑", "artist": "GLAY", "year": 1997, "genre": "ロック", "tags": ["love"]},
        {"title": "LOVEマシーン", "artist": "モーニング娘。", "year": 1999, "genre": "女性アイドル", "tags": ["overall", "money"]},
        {"title": "DEPARTURES", "artist": "globe", "year": 1996, "genre": "J-POP/ダンス", "tags": ["love"]},
        {"title": "SEASONS", "artist": "浜崎あゆみ", "year": 2000, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "夏色", "artist": "ゆず", "year": 1998, "genre": "J-POP", "tags": ["overall"]},
        {"title": "ultra soul", "artist": "B'z", "year": 2001, "genre": "ロック", "tags": ["work", "money"]},
        {"title": "Love, Day After Tomorrow", "artist": "倉木麻衣", "year": 2000, "genre": "J-POP", "tags": ["love"]},
        {"title": "HONEY", "artist": "L'Arc〜en〜Ciel", "year": 1999, "genre": "ロック", "tags": ["love"]},
        {"title": "本能", "artist": "椎名林檎", "year": 1999, "genre": "ロック", "tags": ["overall"]},
        {"title": "CAN YOU CELEBRATE?", "artist": "安室奈美恵", "year": 1997, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "未来へ", "artist": "Kiroro", "year": 1998, "genre": "J-POPバラード", "tags": ["work"]},
        {"title": "チェリー", "artist": "スピッツ", "year": 1996, "genre": "ロック", "tags": ["love"]},
        {"title": "if...", "artist": "DA PUMP", "year": 1998, "genre": "J-POP/ダンス", "tags": ["overall"]},
    ],
    # 55〜64歳向け（1985〜1995年頃）
    "era_1985_1995": [
        {"title": "浪漫飛行", "artist": "米米CLUB", "year": 1990, "genre": "J-POP", "tags": ["overall"]},
        {"title": "パラダイス銀河", "artist": "光GENJI", "year": 1988, "genre": "男性アイドル", "tags": ["overall", "money"]},
        {"title": "瑠璃色の地球", "artist": "松田聖子", "year": 1986, "genre": "女性アイドル", "tags": ["overall"]},
        {"title": "Get Wild", "artist": "TM NETWORK", "year": 1987, "genre": "J-POP/ダンス", "tags": ["work", "money"]},
        {"title": "LADY NAVIGATION", "artist": "B'z", "year": 1992, "genre": "ロック", "tags": ["love"]},
        {"title": "世界が終るまでは...", "artist": "WANDS", "year": 1994, "genre": "ロック/バラード", "tags": ["love"]},
        {"title": "負けないで", "artist": "ZARD", "year": 1993, "genre": "J-POPバラード", "tags": ["work"]},
        {"title": "SAY YES", "artist": "CHAGE and ASKA", "year": 1991, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "それが大事", "artist": "大事MANブラザーズバンド", "year": 1991, "genre": "ロック", "tags": ["work"]},
        {"title": "おどるポンポコリン", "artist": "B.B.クイーンズ", "year": 1990, "genre": "J-POP", "tags": ["overall"]},
        {"title": "ラブ・ストーリーは突然に", "artist": "小田和正", "year": 1991, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "世界中の誰よりきっと", "artist": "中山美穂＆WANDS", "year": 1992, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "シーズン・イン・ザ・サン", "artist": "TUBE", "year": 1986, "genre": "J-POP", "tags": ["overall"]},
        {"title": "慟哭", "artist": "工藤静香", "year": 1992, "genre": "女性アイドル/バラード", "tags": ["love"]},
    ],
    # 65歳以上向け（1970〜1985年頃）
    "era_1970_1985": [
        {"title": "UFO", "artist": "ピンク・レディー", "year": 1977, "genre": "女性アイドル", "tags": ["overall"]},
        {"title": "春一番", "artist": "キャンディーズ", "year": 1978, "genre": "女性アイドル", "tags": ["overall"]},
        {"title": "プレイバックPart2", "artist": "山口百恵", "year": 1978, "genre": "女性アイドル", "tags": ["work", "money"]},
        {"title": "TOKIO", "artist": "沢田研二", "year": 1980, "genre": "J-POP", "tags": ["overall"]},
        {"title": "青い珊瑚礁", "artist": "松田聖子", "year": 1980, "genre": "女性アイドル", "tags": ["love"]},
        {"title": "チャンピオン", "artist": "アリス", "year": 1978, "genre": "フォーク/ロック", "tags": ["work", "money"]},
        {"title": "ひこうき雲", "artist": "荒井由実", "year": 1973, "genre": "J-POP", "tags": ["overall"]},
        {"title": "いとしのエリー", "artist": "サザンオールスターズ", "year": 1979, "genre": "バンド/バラード", "tags": ["love"]},
        {"title": "ふれあい", "artist": "中村雅俊", "year": 1974, "genre": "フォーク", "tags": ["overall"]},
        {"title": "木綿のハンカチーフ", "artist": "太田裕美", "year": 1975, "genre": "J-POPバラード", "tags": ["love"]},
        {"title": "シンデレラ・ハネムーン", "artist": "岩崎宏美", "year": 1978, "genre": "女性アイドル", "tags": ["love"]},
        {"title": "ガンダーラ", "artist": "ゴダイゴ", "year": 1978, "genre": "J-POP", "tags": ["work", "money"]},
        {"title": "どうにもとまらない", "artist": "山本リンダ", "year": 1972, "genre": "女性アイドル", "tags": ["overall"]},
        {"title": "会いたくて会いたくて", "artist": "森昌子", "year": 1972, "genre": "女性アイドル/バラード", "tags": ["love"]},
        {"title": "神田川", "artist": "かぐや姫", "year": 1973, "genre": "フォーク", "tags": ["love"]},
    ],
}

MOOD_REASON_TEMPLATES = {
    "love": "{genre}らしい甘く優しい雰囲気が、今日の恋愛運をそっと後押ししてくれる一曲です。",
    "work": "{genre}ならではの前向きなメッセージが、仕事運と挑戦する気持ちを高めてくれます。",
    "money": "{genre}の高揚感が、金運や成功運を引き寄せるパワーを持つ一曲です。",
    "overall": "{genre}の明るいエネルギーが、今日一日の総合運を盛り上げてくれる一曲です。",
}

MEDALS = ["🥇", "🥈", "🥉"]

# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────
def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def parse_birth(raw: str) -> tuple[str, str]:
    """8桁数字（YYYYMMDD）を検証し (表示用文字列, エラーメッセージ) を返す。"""
    raw = raw.strip()
    if not raw:
        return "", ""
    if not raw.isdigit() or len(raw) != 8:
        return "", "生年月日は8桁の数字で入力してください（例：19810130）"
    yyyy, mm, dd = raw[:4], raw[4:6], raw[6:]
    try:
        datetime(int(yyyy), int(mm), int(dd))
    except ValueError:
        return "", f"日付が正しくありません（入力値：{raw}）"
    return f"{yyyy}年{int(mm)}月{int(dd)}日", ""

def add_section_spacing(text: str) -> str:
    """①レイアウト改善：各運勢セクションの間に空行を入れて見やすくする。"""
    if not text:
        return text
    section_markers = ["🌟", "💕", "💰", "💼", "🍀", "🎨", "🔢", "🎁", "✨"]
    for marker in section_markers:
        text = re.sub(rf"\n(?!\n){re.escape(marker)}", f"\n\n{marker}", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ──────────────────────────────────────────────
# シード生成（優先順位付き）
# ──────────────────────────────────────────────
def make_seed_source(
    today_iso: str,
    user_id: str = "",
    name: str = "",
    birth: str = "",
) -> str | None:
    """
    シードソースをユーザー入力の優先順位に従って生成する。
    ① user_id あり          → today + user_id
    ② name + birth 両方あり → today + name + birth
    ③ name のみ             → today + name
    ④ birth のみ            → today + birth
    ⑤ 全て未入力            → None（エラー）
    """
    if user_id.strip():
        return f"{today_iso}|uid:{user_id.strip()}"
    if name.strip() and birth.strip():
        return f"{today_iso}|{name.strip()}|{birth.strip()}"
    if name.strip():
        return f"{today_iso}|{name.strip()}"
    if birth.strip():
        return f"{today_iso}|{birth.strip()}"
    return None

# ──────────────────────────────────────────────
# 運勢値の決定論的生成
# ──────────────────────────────────────────────
def determine_fortune_values(seed_source: str) -> dict:
    """SHA256ハッシュから運勢の数値を決定論的に生成する。"""
    digest = hashlib.sha256(seed_source.encode("utf-8")).digest()

    def pick(byte_index: int, choices: int) -> int:
        return digest[byte_index % 32] % choices

    return {
        "overall": pick(0, 5) + 1,
        "love":    pick(1, 5) + 1,
        "money":   pick(2, 5) + 1,
        "work":    pick(3, 5) + 1,
        "health":  pick(4, 5) + 1,
        "color":   LUCKY_COLORS[pick(5, len(LUCKY_COLORS))],
        "number":  pick(6, 99) + 1,
        "item":    LUCKY_ITEMS[pick(7, len(LUCKY_ITEMS))],
    }

def get_fortune_id(seed_source: str) -> str:
    """運勢ID（SHA256の先頭8文字）を返す。同じシードなら同じID。"""
    return hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:8]

# ──────────────────────────────────────────────
# GPT出力の検証（改善7）
# ──────────────────────────────────────────────
def verify_fortune_output(text: str, v: dict) -> bool:
    """GPT出力が指定の運勢値と一致するか検証する。"""
    star_checks = [
        (r"🌟総合運\s*\n(★+☆*)", "overall"),
        (r"💕恋愛運\s*\n(★+☆*)", "love"),
        (r"💰金運\s*\n(★+☆*)", "money"),
        (r"💼仕事運\s*\n(★+☆*)", "work"),
        (r"🍀健康運\s*\n(★+☆*)", "health"),
    ]
    for pattern, key in star_checks:
        m = re.search(pattern, text)
        if not m or m.group(1).count("★") != v[key]:
            return False

    color_m = re.search(r"🎨ラッキーカラー\s*\n(.+)", text)
    if not color_m or color_m.group(1).strip() != v["color"]:
        return False

    num_m = re.search(r"🔢ラッキーナンバー\s*\n(\d+)", text)
    if not num_m or int(num_m.group(1).strip()) != v["number"]:
        return False

    item_m = re.search(r"🎁ラッキーアイテム\s*\n(.+)", text)
    if not item_m or item_m.group(1).strip() != v["item"]:
        return False

    return True

def force_correct_values(text: str, v: dict) -> str:
    """検証失敗時に指定値を強制的に上書きする。"""
    text = re.sub(r"(🌟総合運\s*\n)★+☆*", rf"\g<1>{stars(v['overall'])}", text)
    text = re.sub(r"(💕恋愛運\s*\n)★+☆*",  rf"\g<1>{stars(v['love'])}", text)
    text = re.sub(r"(💰金運\s*\n)★+☆*",    rf"\g<1>{stars(v['money'])}", text)
    text = re.sub(r"(💼仕事運\s*\n)★+☆*",  rf"\g<1>{stars(v['work'])}", text)
    text = re.sub(r"(🍀健康運\s*\n)★+☆*",  rf"\g<1>{stars(v['health'])}", text)
    text = re.sub(r"(🎨ラッキーカラー\s*\n).+",   rf"\g<1>{v['color']}", text)
    text = re.sub(r"(🔢ラッキーナンバー\s*\n)\d+", rf"\g<1>{v['number']}", text)
    text = re.sub(r"(🎁ラッキーアイテム\s*\n).+",  rf"\g<1>{v['item']}", text)
    return text

# ──────────────────────────────────────────────
# 🎤 開運カラオケ曲：年齢・運勢に応じた選曲ロジック
# ──────────────────────────────────────────────
def calculate_age(birth_raw: str) -> int | None:
    """YYYYMMDD形式の8桁文字列から満年齢を計算する。未入力ならNone。"""
    birth_raw = (birth_raw or "").strip()
    if not birth_raw.isdigit() or len(birth_raw) != 8:
        return None
    try:
        yyyy, mm, dd = int(birth_raw[:4]), int(birth_raw[4:6]), int(birth_raw[6:])
        birth_date = date(yyyy, mm, dd)
    except ValueError:
        return None
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age

def get_era_key(age: int | None) -> str:
    """年齢から曲データベースの年代キーを返す。年齢不明の場合は中間層を既定値にする。"""
    if age is None:
        age = 30  # 生年月日未入力時の既定値（25〜34歳相当）
    if age <= 24:
        return "current"
    if age <= 34:
        return "era_2015_2025"
    if age <= 44:
        return "era_2005_2015"
    if age <= 54:
        return "era_1995_2005"
    if age <= 64:
        return "era_1985_1995"
    return "era_1970_1985"

def get_mood_key(v: dict) -> str:
    """④運勢のうち最も高い項目に応じて曲の雰囲気（タグ）を決める。"""
    candidates = {
        "overall": v.get("overall", 0),
        "love": v.get("love", 0),
        "work": v.get("work", 0),
        "money": v.get("money", 0),
    }
    # 同点の場合は overall > love > work > money の優先順位にする
    priority = ["overall", "love", "work", "money"]
    best = max(priority, key=lambda k: (candidates[k], -priority.index(k)))
    return best

def pick_songs(era_key: str, mood_key: str, count: int, exclude_titles: list[str]) -> list[dict]:
    """指定の年代・雰囲気タグから、重複なくランダムに曲を選ぶ。"""
    pool = SONG_DATABASE.get(era_key, [])
    exclude_set = set(exclude_titles)

    if mood_key == "overall":
        matched = [s for s in pool if s["title"] not in exclude_set]
    else:
        matched = [s for s in pool if mood_key in s["tags"] and s["title"] not in exclude_set]

    random.shuffle(matched)
    result = matched[:count]

    # マッチする曲だけでは数が足りない場合、同じ年代の他の曲で補う
    if len(result) < count:
        chosen_titles = exclude_set | {s["title"] for s in result}
        remainder = [s for s in pool if s["title"] not in chosen_titles]
        random.shuffle(remainder)
        result += remainder[: count - len(result)]

    return result

def build_song_reason(song: dict, mood_key: str) -> str:
    template = MOOD_REASON_TEMPLATES.get(mood_key, MOOD_REASON_TEMPLATES["overall"])
    return template.format(genre=song["genre"])

def render_song_list(songs: list[dict], mood_key: str) -> str:
    """曲リストをHTML文字列に変換する（song-cardで使用）。"""
    lines = []
    for i, song in enumerate(songs):
        medal = MEDALS[i] if i < len(MEDALS) else "⭐"
        reason = build_song_reason(song, mood_key)
        lines.append(
            f'<div style="margin-bottom:1.1rem;">'
            f'<span class="song-title">{medal} 「{song["title"]}」</span><br>'
            f'<span class="song-meta">{song["artist"]}（{song["year"]}年）・{song["genre"]}</span><br>'
            f'<span class="song-reason">【開運ポイント】{reason}</span>'
            f'</div>'
        )
    return "".join(lines)

# ──────────────────────────────────────────────
# OpenAI呼び出し（モデルフォールバック付き）
# ──────────────────────────────────────────────
def call_openai(system_prompt: str, user_content: str) -> str:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    for model in [OPENAI_MODEL, OPENAI_FALLBACK_MODEL]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=700,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err = str(e).lower()
            if "model" in err or "not found" in err or "does not exist" in err:
                continue
            raise
    raise RuntimeError(
        f"利用可能なモデルがありません（{OPENAI_MODEL} / {OPENAI_FALLBACK_MODEL}）"
    )

# ──────────────────────────────────────────────
# 今日の運勢生成（外部呼び出し可能・改善10）
# ──────────────────────────────────────────────
def generate_today_fortune(
    user_id: str = "",
    name: str = "",
    birth: str = "",
    today_iso: str | None = None,
    today_label: str | None = None,
) -> dict:
    """
    今日の運勢を生成する。外部から呼び出し可能。
    将来的に generate_today_fortune(user_id="rezona_uid") のように使用。

    Returns dict:
        result      : str        表示テキスト
        from_cache  : bool       キャッシュ利用か
        fortune_id  : str | None 運勢ID（8文字）
        values      : dict | None 運勢の数値（カラオケ曲の選曲に使用）
        error       : str | None エラーメッセージ
    """
    if today_iso is None:
        today_iso = date.today().strftime("%Y-%m-%d")
    if today_label is None:
        today_label = date.today().strftime("%Y年%m月%d日")

    seed_source = make_seed_source(today_iso, user_id=user_id, name=name, birth=birth)
    if seed_source is None:
        return {"result": None, "from_cache": False, "fortune_id": None,
                "values": None, "error": "名前または生年月日を入力してください"}

    fortune_id = get_fortune_id(seed_source)
    v = determine_fortune_values(seed_source)
    cache = load_cache()
    cache_key = f"today|{seed_source}"

    if cache_key in cache:
        return {"result": cache[cache_key], "from_cache": True,
                "fortune_id": fortune_id, "values": v, "error": None}

    system = TODAY_SYSTEM_PROMPT.format(
        overall_stars=stars(v["overall"]),
        love_stars=stars(v["love"]),
        money_stars=stars(v["money"]),
        work_stars=stars(v["work"]),
        health_stars=stars(v["health"]),
        color=v["color"],
        number=v["number"],
        item=v["item"],
    )
    user_content = f"今日の日付：{today_label}\n"
    if user_id:
        user_content += f"ユーザーID：{user_id}\n"
    if name:
        user_content += f"名前：{name}\n"
    if birth:
        user_content += f"生年月日：{birth}\n"

    result = None
    last_candidate = ""
    for _ in range(3):
        last_candidate = call_openai(system, user_content)
        if verify_fortune_output(last_candidate, v):
            result = last_candidate
            break

    if result is None:
        result = force_correct_values(last_candidate, v)

    cache[cache_key] = result
    save_cache(cache)
    return {"result": result, "from_cache": False, "fortune_id": fortune_id, "values": v, "error": None}

# ──────────────────────────────────────────────
# 相性占い生成（外部呼び出し可能・改善10）
# ──────────────────────────────────────────────
def generate_compatibility(
    name1: str = "",
    birth1: str = "",
    name2: str = "",
    birth2: str = "",
    today_iso: str | None = None,
    today_label: str | None = None,
) -> dict:
    """
    相性占いを生成する。外部から呼び出し可能。

    Returns dict:
        result      : str
        from_cache  : bool
        fortune_id  : str
        error       : str | None
    """
    if today_iso is None:
        today_iso = date.today().strftime("%Y-%m-%d")
    if today_label is None:
        today_label = date.today().strftime("%Y年%m月%d日")

    seed_source = (
        f"compat|{today_iso}"
        f"|{name1.strip()}|{birth1.strip()}"
        f"|{name2.strip()}|{birth2.strip()}"
    )
    fortune_id = get_fortune_id(seed_source)
    cache = load_cache()

    if seed_source in cache:
        return {"result": cache[seed_source], "from_cache": True,
                "fortune_id": fortune_id, "error": None}

    v = determine_fortune_values(seed_source)
    compat_score = min(60 + (v["overall"] + v["love"]) * 4, 100)

    system = COMPAT_SYSTEM_PROMPT.format(
        compat_stars=stars(round(compat_score / 20)),
        compat_score=compat_score,
        item=v["item"],
    )
    user_content = f"今日の日付：{today_label}\n"
    user_content += f"Aさんの名前：{name1 or '（未入力）'}\n"
    if birth1:
        user_content += f"Aさんの生年月日：{birth1}\n"
    user_content += f"Bさんの名前：{name2 or '（未入力）'}\n"
    if birth2:
        user_content += f"Bさんの生年月日：{birth2}\n"

    result = call_openai(system, user_content)
    cache[seed_source] = result
    save_cache(cache)
    return {"result": result, "from_cache": False, "fortune_id": fortune_id, "error": None}

# ──────────────────────────────────────────────
# Streamlit UI
# ──────────────────────────────────────────────
def main():
    today = date.today()
    today_iso = today.strftime("%Y-%m-%d")
    today_label = today.strftime("%Y年%m月%d日")

    st.markdown('<h1 class="main-title">🔮 くまっち占い</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">くまっちがあなたの運命を読み解きます</p>', unsafe_allow_html=True)

    mode = st.radio(
        "占いの種類",
        ["🌟 今日の運勢", "💑 相性占い"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 今日の運勢 ──────────────────────────────
    if mode == "🌟 今日の運勢":
        with st.form("today_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("👤 名前（任意）", placeholder="例：くまっち")
            with col2:
                birth_raw = st.text_input(
                    "🎂 生年月日（任意）",
                    placeholder="例：19001010",
                    max_chars=8,
                    help="YYYYMMDD形式の8桁数字",
                )
            submitted = st.form_submit_button("🔮 今日の運勢を占う")

        if submitted:
            birth, birth_error = parse_birth(birth_raw)
            if birth_error:
                st.error(birth_error)
            else:
                data = generate_today_fortune(
                    user_id="",
                    name=name,
                    birth=birth,
                    today_iso=today_iso,
                    today_label=today_label,
                )
                if data["error"]:
                    st.warning(data["error"])
                else:
                    # ── 占い結果本体（①レイアウト改善：セクション間に空行）──
                    display_text = add_section_spacing(data["result"])
                    st.markdown(
                        f'<div class="fortune-card">{display_text}</div>',
                        unsafe_allow_html=True,
                    )
                    label = (
                        f"📅 {today_label}の運勢（キャッシュ済み）"
                        if data["from_cache"]
                        else f"📅 {today_label}の運勢"
                    )
                    st.markdown(f'<div class="cache-badge">{label}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="fortune-id-box">🔮 今日の運勢ID<br>'
                        f'<span class="fortune-id-value">{data["fortune_id"]}</span></div>',
                        unsafe_allow_html=True,
                    )

                    # ── 🎤開運カラオケ曲：年齢・運勢に応じて毎回ランダム選曲 ──
                    age = calculate_age(birth_raw)
                    era_key = get_era_key(age)
                    mood_key = get_mood_key(data["values"])

                    # 新しい占い結果が出た（fortune_idが変わった）ときは選曲をリセット
                    if st.session_state.get("song_fortune_id") != data["fortune_id"]:
                        st.session_state["song_fortune_id"] = data["fortune_id"]
                        st.session_state["song_era_key"] = era_key
                        st.session_state["song_mood_key"] = mood_key
                        st.session_state["displayed_songs"] = pick_songs(era_key, mood_key, 5, [])

                    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
                    st.markdown("#### 🎤 今日のラッキーソング")
                    songs = st.session_state["displayed_songs"]
                    song_html = render_song_list(songs, st.session_state["song_mood_key"])
                    st.markdown(f'<div class="song-card">{song_html}</div>', unsafe_allow_html=True)

                    pool_size = len(SONG_DATABASE.get(st.session_state["song_era_key"], []))
                    if len(songs) < pool_size:
                        if st.button("🎵 もっと見る（+5曲）"):
                            more = pick_songs(
                                st.session_state["song_era_key"],
                                st.session_state["song_mood_key"],
                                5,
                                [s["title"] for s in st.session_state["displayed_songs"]],
                            )
                            st.session_state["displayed_songs"] += more
                            st.rerun()

    # ── 相性占い ─────────────────────────────────
    else:
        with st.form("compat_form"):
            st.markdown("**👤 Aさん**")
            col1, col2 = st.columns(2)
            with col1:
                name1 = st.text_input("名前（任意）", placeholder="例：くまっち", key="name1")
            with col2:
                birth1_raw = st.text_input(
                    "生年月日（任意）",
                    placeholder="例：19001010",
                    max_chars=8,
                    help="YYYYMMDD形式の8桁数字",
                    key="birth1",
                )

            st.markdown("**👤 Bさん**")
            col3, col4 = st.columns(2)
            with col3:
                name2 = st.text_input("名前（任意）", placeholder="例：ぱんだ", key="name2")
            with col4:
                birth2_raw = st.text_input(
                    "生年月日（任意）",
                    placeholder="例：19001010",
                    max_chars=8,
                    help="YYYYMMDD形式の8桁数字",
                    key="birth2",
                )
            submitted2 = st.form_submit_button("🔮 相性を占う")

        if submitted2:
            birth1, err1 = parse_birth(birth1_raw)
            birth2, err2 = parse_birth(birth2_raw)
            if err1:
                st.error(f"Aさんの{err1}")
            elif err2:
                st.error(f"Bさんの{err2}")
            else:
                with st.spinner("くまっちが2人の縁を読み解いています...✨"):
                    try:
                        data = generate_compatibility(
                            name1=name1, birth1=birth1,
                            name2=name2, birth2=birth2,
                            today_iso=today_iso,
                            today_label=today_label,
                        )
                        display_text = add_section_spacing(data["result"])
                        st.markdown(
                            f'<div class="fortune-card">{display_text}</div>',
                            unsafe_allow_html=True,
                        )
                        label = (
                            f"📅 {today_label}の相性（キャッシュ済み）"
                            if data["from_cache"]
                            else f"📅 {today_label}の相性"
                        )
                        st.markdown(f'<div class="cache-badge">{label}</div>', unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="fortune-id-box">🔮 今日の運勢ID<br>'
                            f'<span class="fortune-id-value">{data["fortune_id"]}</span></div>',
                            unsafe_allow_html=True,
                        )
                    except Exception as e:
                        st.error(f"占いに失敗しました: {str(e)}")


if __name__ == "__main__":
    main()
