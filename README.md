# 🏀 ESPN Fantasy Basketball Analytics

A Python script to pull ESPN fantasy basketball league data, run advanced calculations, and export everything to Google Sheets.

## 📊 Features

### Stats:
- **Win/Loss Tracking** - Cumulative and weekly rankings of wins, losses, win %
- **Points For/Points Against (PF/PA) Rankings** - Rankings based on cumulative and week-by-week PF and PA
- **PF/PA Differentials** - Weekly and cumulative point differentials
- **Strength of Schedule** - Schedule difficulty based on cumulative PA rankings
- **Injury Impact** - Games missed due to injury and potential points lost
- **Lineup Efficiency** - Points left on the bench/IR when lineup wasn't set

### Google Sheets Export:
- Overview sheet with changelog, documentation, and standings preview
- Standings with cumulative season stats and rankings
- Weekly rankings with week-by-week breakdowns and cumulative stats
- Color scale conditional formatting to optimize visual hierarchy
- Preformatted headers, dividers, and sheets 

## 🚀 Quick Start

### 1. Setup Virtual Environment

```bash
# Navigate to project directory
cd "ESPN Fantasy Basketball Analytics"

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
     - `espn_s2` (looks like `{AVAdTmHCAMkn...}`)
     - `SWID` (looks like `{AB34C6D8-D2G4-1IK4-1K34-JK345KD890R2}`)

#### Google Sheets (Optional - for export):
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Go to API & Services → Library → Enable Google Drive API + Google Sheets API
4. Go to IAM & Admin → Service Accounts
5. Create a service account → Skip Permissions → Skip Principals with access
6. Click on newly created account → Go to Keys → Create JSON key (will auto download json file)
7. Rename the key file to `google-credentials.json` and place it in `config/`
8. Manually create an empty [Google Sheet](https://docs.google.com/sheets) and share it with your service account email with Editor permissions
9. Note the sheet name to use in `.env` file or CLI arg

### 4. Create Environment File

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
```

### 5. Run the Script

```bash
# Run with default settings (uses .env)
python src/main.py

# Override league ID
python src/main.py --league-id 12345678

# Override season year
python src/main.py --year 2026

# Analyze only first 10 weeks
python src/main.py --weeks 10

# Specify Google sheet name
python src/main.py --sheet-name "My Fantasy Sheet"

# Skip Google Sheets export
python src/main.py --skip-export

# Skip stat summary console output
python src/main.py --silent
```

## 📁 Project Structure

```
ESPN Fantasy Basketball Analytics/
├── config/
│   ├── google-credentials.json    # Google service account key (not in git)
│   └── formatting_config.py       # Color and formatting definitions
├── src/
│   ├── __init__.py
│   ├── espn_client.py             # ESPN API wrapper
│   ├── calculations.py            # Stat calculations
│   ├── google_sheets.py           # Google Sheets exporter
│   └── main.py                    # Entry point
├── venv/                          # Virtual environment (not in git)
├── .env                           # Your credentials (not in git)
├── .env.example                   # Template for credentials
├── .gitignore                     # Git ignore file
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## 📈 Available Stats

### Standings Sheet
| Column | Description |
|--------|-------------|
| `team_name` | Team name |
| `team_id` | ESPN team ID |
| `rank` | Current standing (1 = best record) |
| `wins` / `losses` / `ties` | Win-loss-tie record |
| `win_pct` | Win percentage |
| `total_pf` / `total_pa` | Total Points For / Against |
| `avg_pf` / `avg_pa` | Average Points For / Against per week |
| `differential` | Difference between PF and PA |
| `avg_differential` | Average weekly differential |
| `avg_opponent_rank` | Average final rank of opponents faced (lower = tougher schedule) |
| `cumulative_pa_rank` | Running average of PA rank (lower = tougher schedule) |
| Total Injury Stats | Cumulative injury stats across the season |
| `games_missed_injury` | Number of games missed due to injured non-IR players |
| `games_missed_ir` | Number of games missed due to injured IR players |
| `total_games_missed` | Total number of games missed due to injuries on full roster |
| `lost_points_injury` | Potential points lost from injured non-IR players (based on player's avg FPTS) |
| `lost_points_ir` | Potential points lost from IR players (based on player's avg FPTS) |
| `total_lost_points` | Potential points lost from injured players on full roster (based on player's avg FPTS) |
| Average Injury Stats (`avg_*`) | Season averages for the above 6 injury stats |
| Lineup Efficiency | Games missed and points lost due to not setting roster |
| `player_games` | Number of active player games that are starting |
| `bench_games` | Number of active player games that are left on the bench if active roster spot is available and player scored above 0 |
| `ir_games` | Number of active player games that are left on the bench if active roster spot is available and player scored above 0 |
| `total_missed_games` | Total number of active player games missed from bench or IR players |
| `bench_points_lost` | Points lost from bench players that could have started |
| `ir_points_lost` | Points lost from IR players that could have started |
| `total_points_lost` | Total points lost from bench and IR players |
| Average Lineup Effiency (`avg_*`) | Season averages for the samabove e 6 player effiency stats |

### Weekly Rankings Sheet
| Column | Description |
|--------|-------------|
| `week` | Week number |
| `team_name` | Team name |
| `team_id` | ESPN team ID |
| `opponent_name` | Name of opponent's team |
| `rank` | Cumulative standing up to that week |
| `wins` / `losses` / `ties` | Cumulative win-loss-tie record up that week |
| `win_pct` | Cumulative win percentage up to that week |
| `pf` | Points scored that week |
| `pa` | Points opponent scored that week |
| `pf_rank` \ `pa_rank` | PF/PA rank that week |
| `differential` | Difference between PF and PA |
| `cumulative_pf` / `cumulative_pa` | Cumulative Points For / Against up to that week |
| `cumulative_pf_rank` | Running average of weekly PF ranks (lower = more consistent high scorer) |
| `cumulative_pa_rank` | Running average of weekly PA ranks (lower = consistently faced high scorers) |
| `cumulative_differential` | Cumulative point differential |
| Weekly Total Injury Stats | Weekly injury stats |
| `games_missed_injury` | Number of games missed due to injured non-IR players that week |
| `games_missed_ir` | Number of games missed due to injured IR players that week |
| `total_games_missed` | Total number of games missed due to injuries on full roster that week |
| `lost_points_injury` | Potential points lost from injured non-IR players that week (based on player's avg FPTS) |
| `lost_points_ir` | Potential points lost from IR players that week (based on player's avg FPTS) |
| `total_lost_points` | Potential points lost from injured players on full roster that week (based on player's avg FPTS) |
| Cumulative Injury Stats (`cumulative_*`) | Weekly running totals for the above 6 injury stats |
| Lineup Efficiency | Weekly games missed and points lost due to not setting roster |
| `player_games` | Number of active player games that are starting that week |
| `bench_games` | Number of active player games that are left on the bench that week if active roster spot is available and player scored above 0 |
| `ir_games` | Number of active player games that are left on the bench that week if active roster spot is available and player scored above 0 |
| `total_missed_games` | Total number of active player games missed from bench or IR players that week |
| `bench_points_lost` | Points lost from bench players that could have started that week |
| `ir_points_lost` | Points lost from IR players that could have started that week |
| `total_points_lost` | Total points lost from bench and IR players that week |


## 🛠️ Troubleshooting

### "Failed to connect to ESPN league"
- Check your League ID is correct
- For private leagues, ensure ESPN_S2 and SWID cookies are current (they expire ~2 weeks)
- Try refreshing the cookies from your browser

### "Failed to authenticate with Google Sheets"
- Verify `config/google-credentials.json` exists
- Ensure the service account has access to Google Sheets and Drive APIs
- Share your Google Sheet with the service account email
- Check Google Drive storage quota is not exceeded

### "Google Drive storage quota has been exceeded"
- The service account has its own 15GB Drive quota
- Try manually creating the sheet in your Drive and sharing it with the service account
- Or use an existing sheet that already has space

### "Module not found" errors
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

## 📝 Notes

- ESPN data is pulled in real-time from ESPN's API
- Private league cookies may expire periodically (~2 weeks), so may need to refresh them
- Google Sheets API has rate limits (300 requests/60 seconds)
- Injury tracking is based on roster slots and injury status at game time
- Lineup efficiency counts points left on bench/IR only when your active starters had fewer than 10 players scoring > 0 points that day
- Bronny James is excluded from injury tracking (auto-filtered)

## 🤝 Contributing

Feel free to submit issues or feature requests!

## 📄 License

MIT License - Feel free to use and modify as needed.

