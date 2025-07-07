# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# History settings - the essential configuration
HISTCONTROL=ignoreboth        # ignore duplicate lines and lines starting with space
HISTSIZE=10000               # number of lines to keep in memory
HISTFILESIZE=20000           # number of lines to keep in history file
HISTTIMEFORMAT="%Y-%m-%d %T " # add timestamps to history

# Append to the history file, don't overwrite it
shopt -s histappend

# Save history after each command to ensure it's preserved
PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"

# Basic shell options for usability
shopt -s checkwinsize  # update LINES and COLUMNS after each command
shopt -s globstar      # enable ** pattern for recursive matching
shopt -s cdspell       # auto-correct minor typos in directory names

# Basic color support for ls and grep (lightweight)
if [ -x /usr/bin/dircolors ]; then
    eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
fi

# Essential aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.

if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# Simple colored prompt
case "$TERM" in
    xterm-color|*-256color) 
        PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
        ;;
    *)
        PS1='\u@\h:\w\$ '
        ;;
esac

export POETRY_VIRTUALENVS_IN_PROJECT=false
export POETRY_VIRTUALENVS_PATH=/home/devuser/.cache/pypoetry/virtualenvs

# Welcome message
echo "🚗💨 Welcome to StreetRace Development Environment!"
echo "📁 Working directory: $(pwd)"
echo "🐍 Python version: $(python --version)"
echo "📦 Poetry version: $(poetry --version)"
echo "🎯 Run 'check' to verify everything works"
echo "🔧 Use 'pi' to install dependencies with Poetry"
echo "🔍 Use 'sr' or 'streetrace' to run the StreetRace CLI"
echo "💡 Type 'help' for useful commands and aliases"