# How to Access Our Server (for Dummies)
> This guide will get you into our GCP (Google Cloud) server even if you have no idea what you're doing. Just follow each step exactly.

---

## What is this even?

Our website and AI models run on a **server** — basically a computer that lives in Google's data center in Europe. To work on it, you need to connect to it from your laptop. This guide shows you how.

Think of it like this:
- 🖥️ The **VM (Virtual Machine)** = our remote computer in the cloud
- 🔑 The **SSH key** = your personal key to get in (like a house key)
- 💻 **Terminal** = the app on your Mac where you type commands

---

## Before You Start

- You need a **Mac** (if you have Windows, ask Mayood)
- You need to be added to the **Google Cloud project** — ask Mayood to add you
- Open the **Terminal** app on your Mac (press `Cmd + Space`, type "Terminal", hit Enter)

---

## Step 1 — Create Your SSH Key (your key to get in)

An SSH key is just a file on your computer that proves who you are. You only do this **once ever**.

In Terminal, run:

```bash
ssh-keygen -t ed25519
```

It will ask you 3 questions. Just hit **Enter** each time (don't type anything).

When you see some weird art made of characters, you're done. ✅

---

## Step 2 — Install the Google Cloud Tool

This installs `gcloud`, the tool that lets you talk to Google Cloud from your Terminal.

```bash
brew install --cask google-cloud-sdk
```

Then run these two lines so your Terminal knows where to find it:

```bash
echo 'source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"' >> ~/.zshrc
source ~/.zshrc
```

Check it worked:

```bash
gcloud --version
```

You should see something like `Google Cloud SDK 558.0.0`. ✅

> **Don't have brew?** Run this first:
> ```bash
> /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
> ```

---

## Step 3 — Log In to Google Cloud

```bash
gcloud auth login
```

A browser window will open. Sign in with your **Google account** (the one that was added to the project).

Then set the project:

```bash
gcloud config set project innovacx
```

You'll see a warning about an "environment tag" — just ignore it. ✅

---

## Step 4 — Add Your Key to the Server

This tells the server "hey, this person is allowed in."

```bash
gcloud compute instances add-metadata innovacx-vm \
  --zone europe-west1-b \
  --metadata ssh-keys="YOUR_NAME:$(cat ~/.ssh/id_ed25519.pub)"
```

⚠️ Replace `YOUR_NAME` with your actual name (no spaces, lowercase). For example: `ali`, `leeno`, `majid`.

You should see: `Updated [https://www.googleapis.com/...]` ✅

---

## Step 5 — Connect to the Server

```bash
gcloud compute ssh innovacx-vm --zone europe-west1-b
```

If it worked, your Terminal prompt will change to something like:

```
yourname@innovacx-vm:~$
```

**You're in!** 🎉 You are now inside our server.

---

## Step 6 — Go to the Project Folder

Once you're inside the server, go to our project:

```bash
cd /opt/innova-cx
```

Then type `ls` to see all the files:

```bash
ls
```

You should see folders like `backend`, `frontend`, `data`, etc. ✅

---

## You're Done! 🙌

Every time you want to get back in, you just need **Step 5**:

```bash
gcloud compute ssh innovacx-vm --zone europe-west1-b
```

---

## Quick Reference Card

| Thing | Value |
|---|---|
| Server name | `innovacx-vm` |
| Location | `europe-west1-b` |
| Project | `innovacx` |
| Project folder | `/opt/innova-cx` |

---

## Something Broke?

| Problem | Fix |
|---|---|
| `command not found: gcloud` | Redo Step 2 |
| `You do not have an active account` | Redo Step 3 |
| `Permission denied` | Ask Mayood to add your key |
| You see `$` but nothing works | You might still be on your own Mac — did Step 5 work? |

---

*Made with love for the innova-cx team 💙*
