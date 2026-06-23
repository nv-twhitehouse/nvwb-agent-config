#!/bin/bash

# This is for automatic behavior on ending a session. 

# Claude Code has a clunky approach to auth that uses ~/.claude.json in the home folder
# instead of a file in ~/.claude/. Since we shouldn't mount the entire ~ folder, this necessitates
# moving the file in and out of a persistent mount.

cp ~/.claude.json ~/.claude/.claude.json

