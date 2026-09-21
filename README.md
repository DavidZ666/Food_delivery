# Food Delivery

A food delivery application built with Python for COSC 310.

## Getting Started

After accepting the GitHub invitation, follow these steps to set up the project and contribute.

### 1. Clone the Repository

Clone the repository and open the project folder in VS Code. Replace the placeholders below with the actual repository URL and folder name.

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Set Up a Virtual Environment

Each team member should create their own local virtual environment.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Install dependencies**

With the virtual environment activated, run:

```bash
python -m pip install -r requirements.txt
```

All team members should use the same agreed Python version. Record this version in the README.

### 3. Keep Local Environment Files Out of Git

**Do not push your `.venv` folder to GitHub.** Each person creates it locally.

Our `.gitignore` should include:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.env
```

We **do commit `requirements.txt`** so everyone can install the project dependencies. If you add a dependency, update this file.

Never commit passwords, tokens, or API keys.

### 4. Create a Feature Branch

Coordinate your task on the GitHub Project Board before starting.

With a clean working directory, update `main` and create a branch:

```bash
git switch main
git pull origin main
git switch -c feature/your-task
```

Name your branch after the task, such as `feature/restaurant-list`.

**Do not commit implementation changes directly to `main`.**

### 5. Test, Commit, and Push

Once the test suite is available, run:

```bash
python -m pytest
```

Review your changes:

```bash
git status
git diff
```

Stage only the intended files, then commit and push your branch:

```bash
git add <files-you-changed>
git commit -m "Describe your changes"
git push -u origin feature/your-task
```

### 6. Open a Pull Request

On GitHub:

1. Open a Pull Request from your feature branch into `main`.
2. Explain what changed and how you tested it.
3. Request a teammate's review.
4. Address review comments and resolve failing checks.
5. Merge after review and successful checks.

Do not approve your own Pull Request.

## Team Workflow

**Issue → Feature Branch → Code and Tests → Pull Request → Peer Review → Merge**

Use the GitHub Project Board to coordinate work and track progress. Every team member should be able to explain the code they contribute or review.