# Food_delivery
A food delivery application built with Python for COSC 310.

Hi everyone! After accepting the GitHub invitation, please follow these steps:

1. Clone the repository and open it in VS Code.

git clone <repository-url>
cd <repository-folder>

2. Create your own local Python virtual environment.
On macOS/Linux:

python3 -m venv .venv
source .venv/bin/activate

On Windows PowerShell:

py -m venv .venv
.\.venv\Scripts\Activate.ps1

Then install the project dependencies:

python -m pip install -r requirements.txt

We should use the same Python version, as specified in the README.

3. Do not push your virtual environment to GitHub.
Each person creates their own .venv locally. Make sure our .gitignore includes:

.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.env

We do commit requirements.txt, so everyone can install the same dependencies. If you add a dependency, update that file. Never commit passwords, tokens, or API keys.

4. Create a feature branch before making changes.
Start with a clean working directory, then run:

git switch main
git pull origin main
git switch -c feature/your-task

Name your branch after the task, such as feature/restaurant-list. Please do not commit implementation changes directly to main.

5. Test your changes, commit, and push your branch.
Once the test suite is available, run:
python -m pytest
Review your changes with git status and git diff, then stage only the intended files:

git add <files-you-changed>
git commit -m "Describe your changes"
git push -u origin feature/your-task

6. Open a Pull Request on GitHub.
Set main as the target branch, explain what changed and how you tested it, and request a teammate’s review. Do not approve your own PR. Merge after review and successful checks.
Please coordinate tasks on the GitHub Project Board before starting, and make sure you can explain the code you contribute or review.