# 🔗 LinkedIn-to-GitHub

> **Bridge Your Professional Network**: Seamlessly connect your **LinkedIn** network to **GitHub** and discover where your colleagues build.

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen?style=flat-square)
![Code Quality](https://img.shields.io/badge/code%20quality-A-brightgreen?style=flat-square)
![Awesome Opencode](https://img.shields.io/badge/awesome-opencode-FF1493?style=flat-square)

## Table of Contents

- 🌟 [Features](#features)
- 📚 [Beginner's Guide](#beginners-guide)
- 🚀 [Quick Start](#quick-start)
- 📋 [Requirements](#requirements)
- 🛠️ [Installation](#installation)
- 🎯 [How to Export from LinkedIn](#how-to-export-from-linkedin)
- 🔗 [Complete Workflow](#complete-workflow)
- 🎨 [Using the Dashboard](#using-the-dashboard)
- 🧪 [Testing](#testing)
- 🔧 [Troubleshooting](#troubleshooting)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **📊 Smart CSV Parsing** | Robust Pydantic-powered handling of LinkedIn exports with error handling |
| **🔍 Automated Discovery** | Heuristic-based GitHub API search using name + company for matches |
| **🎨 Modern Dashboard** | Interactive HTML interface with dark mode and real-time search |
| **⚡ Batch Operations** | Follow multiple users at once using GitHub CLI |
| **🛡️ Rate Limit Protection** | Intelligent handling of API limits with auto token detection |
| **✅ Smart Deduplication** | Automatic detection and handling of duplicate usernames |
| **📧 No Email Required** | Works even when LinkedIn export doesn't include email addresses |

---

## 📚 Beginner's Guide

**New to this tool?** Here's what it does in simple terms:

1. **Export** your LinkedIn connections (they give you a CSV file)
2. **Run** the tool to create a searchable dashboard
3. **Search** for your connections on GitHub using the dashboard
4. **Review** and manually verify GitHub usernames
5. **Follow** them all at once on GitHub

**Why would you use this?**
- 👥 You want to follow your professional network on GitHub
- 🔍 Manually searching for 100+ people would take forever
- 🤖 This tool automates the tedious part
- 💡 You still review everything before following (not fully automated)

**What you need:**
- A CSV export from LinkedIn
- Python 3.10+ on your computer
- (Optional) GitHub CLI for the final sync step
- (Optional) GitHub Personal Access Token for faster searching

---

## 🚀 Quick Start

### For the Impatient (5 minutes)

```bash
# 1. Install
git clone https://github.com/irvani/linkedin-to-github.git
cd linkedin-to-github
make dev

# 2. Export LinkedIn connections (see section below)
# Save it as: Connections.csv

# 3. Initialize
ltg init --connections Connections.csv

# 4. Open in browser
open github_lookup_links.html

# 5. Review & sync (optional)
ltg sync --worklist github_lookup_worklist.csv --yes
```

---

## 📋 Requirements

### Essential
- **Python**: 3.10 or newer
- **LinkedIn Connections Export**: CSV file from your LinkedIn account
- **A few minutes** of your time

### Optional but Helpful
- **[GitHub CLI](https://cli.github.com/)** - For `ltg sync` command
  - Allows you to actually follow people from the command line
  - If you skip this, you can still see the list to follow manually
  
- **[GitHub Personal Access Token](https://github.com/settings/tokens/new)** - For faster searching
  - Makes searches ~80x faster (5000 vs 60 requests/hour)
  - Takes 2 minutes to create
  - Only needs `read:user` permission (minimum security)

---

## 🛠️ Installation

### Option 1: From Source (Recommended for Beginners)

```bash
# Clone the repository
git clone https://github.com/irvani/linkedin-to-github.git
cd linkedin-to-github

# Install with development dependencies
make dev

# Verify installation
ltg --help
```

### Option 2: From PyPI (When Published)

```bash
pip install linkedin-to-github
ltg --help
```

### Verify Everything Works

```bash
# Should show command help
ltg init --help
ltg search --help
ltg sync --help
```

---

## 🎯 How to Export from LinkedIn

### Step-by-Step (Works as of January 2026)

#### **Step 1: Go to Your Connections**
1. Log in to [LinkedIn](https://www.linkedin.com)
2. Click on **"My network"** at the top (or go to [linkedin.com/mynetwork](https://www.linkedin.com/mynetwork))
3. Click **"Connections"** in the left sidebar

#### **Step 2: Download Your Connections**
1. In the top right corner, look for **"Manage synced contacts"** button (or **"Export"**)
2. Click on **"Export contacts"** (or **"Export LinkedIn connections"**)
3. LinkedIn will show you export options

#### **Step 3: Download as CSV**
1. Select **CSV** format (not vCard or Outlook)
2. Click **Download** or **Export**
3. Save the file as **`Connections.csv`** in your project folder

#### **Where to Save It**
```
linkedin-to-github/
├── Connections.csv        ← Save your export here
├── src/
├── tests/
└── README.md
```

### 📝 Important Notes About LinkedIn Exports

#### ⚠️ Email addresses might be missing!
- LinkedIn only includes email addresses if contacts have made them public
- Don't worry - **the tool works fine without emails**
- Searches by name + company are actually MORE reliable

#### ✅ What's included in the export:
- First Name, Last Name
- LinkedIn Profile URL
- Email Address *(may be empty)*
- Company
- Position/Job Title
- Connected On (date)

#### ❌ What's NOT included:
- Email address (often missing due to privacy settings)
- GitHub username (we find this for you)
- Phone numbers
- Other contact info

#### Example Export File

Your `Connections.csv` should look like this:

```csv
First Name,Last Name,URL,Email Address,Company,Position,Connected On
Alice,Johnson,https://www.linkedin.com/in/alice-johnson,alice@example.com,Google,Software Engineer,Jan 15 2024
Bob,Smith,https://www.linkedin.com/in/bob-smith,,Microsoft,Product Manager,Feb 20 2024
Carol,Davis,https://www.linkedin.com/in/carol-davis,carol@acme.com,GitHub,Developer Advocate,Mar 10 2024
```

**Notice:** Bob Smith has NO email address. That's normal! The tool handles this gracefully. ✅

---

## 🔗 Complete Workflow

### Command 1: `ltg init` - Initialize and Create Dashboard

**What it does:**
- Reads your LinkedIn export (Connections.csv)
- Validates the data
- Creates two output files

**Usage:**
```bash
ltg init --connections Connections.csv
```

**Output files created:**

1. **`github_lookup_worklist.csv`** - Spreadsheet for tracking
   - Columns: name, company, position, GitHub username, notes, search links
   - Edit the "github_username" column with GitHub profiles you find
   
2. **`github_lookup_links.html`** - Interactive dashboard
   - Search in real-time (press `/` to search)
   - Click links to search Google and GitHub
   - Dark mode support
   - Works offline

**Time:** < 1 second for 500 connections

---

### Command 2: `ltg search` - Auto-Find GitHub Profiles (Optional)

**What it does:**
- Searches GitHub for your connections automatically
- Uses their name + company for accurate matches
- Fills in the CSV with matches
- Uses GitHub API (respects rate limits)

**Usage:**
```bash
# Using your GitHub CLI authentication (recommended)
ltg search --connections Connections.csv

# Or provide token directly
ltg search --connections Connections.csv --token ghp_xxxxxxxxxxxx

# Force overwrite if you ran this before
ltg search --connections Connections.csv --overwrite
```

**How it works:**
1. **Priority 1**: Search for "name + company" on GitHub
   - Confidence: 90% (if only 1 match) or 70% (if multiple matches)
2. **Fallback**: Search for just "name" on GitHub
   - Confidence: 40% (less reliable)

**Confidence Scores:**
```
0.9 = Probably correct (exact match with company)
0.7 = Likely correct (one of several matches)
0.4 = Maybe correct (name only, could be anyone)
0.0 = Not found (manual search needed)
```

**Rate Limits:**
- **Without token**: 60 searches/hour (~1 per minute)
- **With token**: 5000 searches/hour (~80 per minute)
- Tool continues even if you hit the limit

**Time:** 5-15 minutes for 500 connections (depends on token)

---

### Command 3: `ltg sync` - Follow on GitHub

**What it does:**
- Actually follows people on GitHub
- Uses GitHub CLI (`gh` command)
- Shows a preview before executing

**Requirements:**
- GitHub CLI installed: `brew install gh` (macOS)
- Logged in: `gh auth login`

**Usage:**
```bash
# Preview what will happen (dry run)
ltg sync --worklist github_lookup_worklist.csv

# Actually follow (confirmation required)
ltg sync --worklist github_lookup_worklist.csv --yes
```

**Preview output:**
```
Plan: Follow 47 users on GitHub.
  - @alice-johnson
  - @bob-smith
  - @carol-davis
  ... and 44 others.
Run with --yes to confirm.
```

**Time:** < 1 second to follow everyone

---

## 🎨 Using the Dashboard

### How to Find Someone's GitHub Profile

1. **Open** `github_lookup_links.html` in your browser
2. **Search** for someone by name (or press `/`)
3. **Click** one of the search links:
   - 🔍 **Google** - Google for "name github"
   - 🔍 **Google Company** - Google for "name company github"
   - 🔗 **GitHub** - Search GitHub directly for "name company"
4. **Click** their profile link when you find them
5. **Copy** their GitHub username: `@their-username`
6. **Paste** into the CSV in the "github_username" column

### Dashboard Features

- 🔍 **Real-time search** - Type to filter instantly
- 🌙 **Dark mode** - Respects your system preference
- 📱 **Mobile-friendly** - Works on phone/tablet
- ⌨️ **Keyboard shortcut** - Press `/` to search
- 🔗 **Quick links** - Direct to LinkedIn, Google, GitHub Search

---

## 🧪 Testing

```bash
# Run all tests
make test

# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_make_outputs.py::test_parse_and_outputs -v

# Check code quality
make lint

# Clean up
make clean
```

**All tests passing:**
```
✅ tests/test_make_outputs.py::test_parse_and_outputs PASSED
✅ tests/test_make_outputs.py::test_read_following_list PASSED
====== 2 passed in 0.15s ======
```

---

## 🔧 Troubleshooting

### "CSV header not found"

**Error:**
```
ValueError: Target header not found. Expected: First Name,Last Name,URL,Email Address...
```

**Solution:**
1. ✅ Verify it's a LinkedIn export (don't edit it manually)
2. ✅ Save it with UTF-8 encoding
3. ✅ Make sure the header row is intact
4. ✅ Rename it to `Connections.csv` (exact name)

**Check your file:**
```bash
head -1 Connections.csv
# Should show: First Name,Last Name,URL,Email Address,Company,Position,Connected On
```

---

### "GitHub CLI not found"

**Error:**
```
FileNotFoundError: GitHub CLI ('gh') not found. Install from: https://cli.github.com/
```

**Solution:**
```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Verify
gh --version

# Authenticate
gh auth login
```

---

### "API rate limit hit"

**Error:**
```
GitHub API rate limit hit. Using PAT token is recommended.
```

**Why it happened:**
- You searched without a GitHub token
- GitHub limits unauthenticated searches to 60/hour

**Solution - Create a Personal Access Token:**
1. Go to [github.com/settings/tokens/new](https://github.com/settings/tokens/new)
2. Name it: `linkedin-to-github`
3. Select scope: `read:user` only (minimum permission)
4. Generate token
5. Copy the token (you'll only see it once)

**Use the token:**
```bash
ltg search --connections Connections.csv --token ghp_xxxxxxxxxxxx
```

This increases your limit to **5000/hour** (~80x faster). ⚡

---

### Email addresses are missing

**Why:**
- LinkedIn only exports emails if the person made them public
- This is normal and happens a lot (privacy settings)

**Is it a problem?**
- ❌ No! The tool works perfectly without emails
- ✅ Searches by name + company are actually MORE reliable
- ✅ You can still find everyone on GitHub

**What to do:**
If you need someone's email, try:
- Search them on GitHub (often in their profile)
- Check their LinkedIn profile directly
- Look for GitHub profile links in their LinkedIn "About" section

---

### Slow search performance

**Cause:** Searching without a GitHub token (60/hour limit)

**Solution:** Use a Personal Access Token (see above)

With token: **80x faster** ⚡

---

## 🤝 Contributing

**Want to help?** Here are some areas we'd love contributions for:

- 🎯 Fuzzy name matching for edge cases
- 👥 Mutual connections detection
- 📝 Bio analysis for job title matching
- 💻 Web UI (instead of HTML file)
- 📤 Export to JSON/Markdown
- 🚀 Unfollow management

**Development setup:**
```bash
git clone https://github.com/irvani/linkedin-to-github.git
cd linkedin-to-github
make dev      # Install dependencies
make test     # Run tests
make lint     # Check code quality
```

---

## 📄 License

MIT - See [LICENSE](LICENSE) for details

---

## 🙌 Built With

- [Pydantic V2](https://docs.pydantic.dev/) - Data validation
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Rich](https://rich.readthedocs.io/) - Terminal UI

---

## 📞 Support

- 📖 [Read the docs](#table-of-contents)
- 🐛 [Report issues](https://github.com/irvani/linkedin-to-github/issues)
- 💡 [Suggest features](https://github.com/irvani/linkedin-to-github/issues/new)

---

## 🔗 Quick Links

- **LinkedIn** 🔗 - [linkedin.com](https://linkedin.com) - Export your connections
- **GitHub** 🐙 - [github.com](https://github.com) - Find and follow people
- **GitHub CLI** - [cli.github.com](https://cli.github.com) - Command-line tool
- **Awesome Opencode** - Quality automation projects

---

**Made with ❤️ to help you grow your GitHub network**

**Star us if you find this useful!** ⭐
