#!/bin/sh -e
# Install venv and run teleglobe

root_dir=$(dirname "$0")

if [ -f "update.zip" ]; then
    if ! unzip -l "update.zip" | grep -q teleglobe.sh; then
        echo "The update archive is corrupted, skip the update"
        rm -f "update.zip"
    fi
fi

# Restore backup in case something bad happened
if [ -f ".update_in_progress" -o ! -f "update.zip" -a -f "backup.tar.gz" ]; then
    echo "Update failed, restore backup"
    rm -rf "${root_dir}"/* "${root_dir}"/.* || true
    tar xf "backup.tar.gz" -C "${root_dir}"

    rm -f .update_in_progress "backup.tar.gz"

    echo "Backup unpacked, restart the daemon"
    exit
fi

# Update procedure in progress
if [ -f "update.zip" ]; then
    if [ ! -f "backup.tar.gz" ]; then
        echo "Running update procedure"
        # Clean and backup
        rm -rf "${root_dir}/__pycache__"
        tar czf backup.tar.gz -C "${root_dir}" .

        rm -rf "${root_dir}"/* "${root_dir}"/.* || true

        echo "Unpack update to teleglobe directory"
        unzip -d "${root_dir}" update.zip
        chmod +x "${root_dir}/teleglobe.sh"

        echo "Update unpacked, restart the daemon"
        exit
    else
        # Backup is here, remove update.zip and start as usual
        rm -f update.zip
        # Delete old backup files and except for 5 latest
        find -name 'backup-*' | sort -u | head -n -5 | xargs rm -f
        echo "Run the new version of TeleGlobe"
    fi
fi

# Setup virtual environment
echo "Ensuring here is venv installed"
[ -f ".venv/bin/activate" ] || python3 -m venv ".venv"

. ".venv/bin/activate"
if [ ! -f ".last_update" -o "${root_dir}/requirements.txt" -nt ".last_update" ]; then
    echo "Install the requirements"
    pip install -r "${root_dir}/requirements.txt"
    touch .last_update
else
    echo "Requirements already installed"
fi

# Run teleglobe
echo "Running TeleGlobe"
python3 -u "${root_dir}/teleglobe.py"
