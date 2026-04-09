@echo off
git add apps/users/templates/users/signup.html
git status
echo.
echo Sekarang menjalankan commit...
git commit -m "Resolve merge conflicts: remove undefined password_confirm variable and duplicate Command class"
git status
