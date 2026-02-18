# 🏀 ESPN Fantasy Basketball Analytics

A Python script to pull ESPN fantasy basketball league data, run advanced calculations, and export everything to Google Sheets.

## 📊 Features

### Statistics Calculated:
- **Games Missed Due to Injury** - Track players who were injured/out while on your roster
- **IR Slot Analysis** - Count games missed and lost points from IR players
- **Weekly PF/PA Rankings** - See how your team ranked each week
- **Toughest Opponent Rank** - Based on weekly PF ranks (lower = tougher opponent)
- **PF/PA Differentials** - Weekly and cumulative point differentials
- **Luck Factor** - Compare actual wins to expected wins
- **Consistency Score** - Measure how consistent your team's scoring is

### Google Sheets Export:
- Standings with gold/silver/bronze formatting
- Weekly rankings and cumulative stats
- Toughest opponents analysis
- Injury analysis
- Luck factor tracking
- Consistency metrics
- Summary dashboard

## 🚀 Quick Start

### 1. Setup Virtual Environment

```bash
# Navigate to project directory
cd "ESPN Fantasy Basketball"

# Create virtual environment
py -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

#### ESPN (Required):
1. Log into [ESPN Fantasy](https://fantasy.espn.com/)
2. Navigate to your basketball league
3. Get your **League ID** from the URL: `https://fantasy.espn.com/basketball/league?leagueId=12345`
4. For private leagues, get your cookies:
   - Press F12 to open DevTools
   - Go to Application/Storage → Cookies → https://fantasy.espn.com
   - Copy values for:
     - `espn_s2` (long string)
     - `SWID` (looks like `{12345678-1234-1234-1234-123456789012}`)

#### Google Sheets (Optional - for export):
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to IAM & Admin → Service Accounts
5. Create a service account → Download JSON key
6. Rename the key file to `google-credentials.json` and place it in `config/`

### 4. Create Environment File

Copy the example file and fill in your credentials:

```bash
copy .env.example .env
```

Edit `.env` with your information:

```env
# ESPN Credentials
ESPN_LEAGUE_ID=12345678
ESPN_S2=your_espn_s2_cookie_here
ESPN_SWID=your_swid_here
ESPN_YEAR=2025

# Google Sheets
GOOGLE_CREDENTIALS_PATH=./config/google-credentials.json
GOOGLE_SHEET_NAME=ESPN Fantasy Basketball Analytics
GOOGLE_USER_EMAIL=your_email@gmail.com
```

### 5. Run the Script

```bash
# Run with default settings (uses .env)
python src/main.py

# Analyze only first 10 weeks
python src/main.py --weeks 10

# Skip Google Sheets export
python src/main.py --skip-export

# Override league ID
python src/main.py --league-id 12345678
```

## 📁 Project Structure

```
ESPN Fantasy Basketball/
├── config/
│   └── google-credentials.json    # Google service account key (not in git)
├── src/
│   ├── __init__.py
│   ├── espn_client.py             # ESPN API wrapper
│   ├── calculations.py            # Stat calculations
│   ├── google_sheets.py           # Google Sheets exporter
│   └── main.py                    # Entry point
├── venv/                          # Virtual environment
├── .env                           # Your credentials (not in git)
├── .env.example                   # Template for credentials
├── .gitignore                     # Git ignore file
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## 📈 Available Calculations

### Weekly Rankings Tab
| Column | Description |
|--------|-------------|
| week | Week number |
| pf | Points For |
| pa | Points Against |
| pf_rank | Rank by PF (1 = highest) |
| pa_rank | Rank by PA (1 = lowest) |
| differential | PF - PA |

### Toughest Opponents Tab
| Column | Description |
|--------|-------------|
| opponent_pf_rank | Opponent's PF rank that week |
| cumulative_avg_opp_rank | Average opponent rank (lower = tougher schedule) |

### Injury Analysis Tab
| Column | Description |
|--------|-------------|
| games_missed_injury | Active roster players who didn't play (injured) |
| games_missed_ir | Players in IR slot |
| lost_points_injury | Estimated points lost from injured active players |
| lost_points_ir | Estimated points lost from IR players |

### Luck Factor Tab
| Column | Description |
|--------|-------------|
| expected_wins | Expected wins based on PF vs all teams |
| luck_factor | Actual result - expected (positive = lucky) |
| cumulative_luck | Total luck for the season |

### Consistency Tab
| Column | Description |
|--------|-------------|
| avg_pf | Average Points For |
| std_pf | Standard deviation of PF |
| consistency_score | std_pf / avg_pf (lower = more consistent) |
| range | max_pf - min_pf |

## 🛠️ Troubleshooting

### "Failed to connect to ESPN league"
- Check your League ID is correct
- For private leagues, ensure ESPN_S2 and SWID cookies are current (they expire ~2 weeks)
- Try refreshing the cookies from your browser

### "Failed to authenticate with Google Sheets"
- Verify `config/google-credentials.json` exists
- Ensure the service account has access to Google Sheets and Drive APIs
- Share your Google Sheet with the service account email

### "Module not found" errors
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

## 📝 Notes

- ESPN data is pulled in real-time from ESPN's API
- Private league cookies expire periodically (~2 weeks), you'll need to refresh them
- Google Sheets API has rate limits (300 requests/60 seconds)
- Injury tracking is based on roster slots and injury status at game time

## 🤝 Contributing

Feel free to submit issues or feature requests!

## 📄 License

MIT License - Feel free to use and modify as needed.

---

**Enjoy dominating your fantasy league! 🏆**
