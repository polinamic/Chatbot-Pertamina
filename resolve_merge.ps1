#!/usr/bin/env pwsh
cd c:\Tugas\Magang\Chatbot-Pertamina
git add apps/users/views.py apps/users/management/commands/create_admin.py
git commit -m "Resolve merge conflicts: remove undefined password_confirm variable and duplicate Command class"
git status
