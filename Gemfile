# frozen_string_literal: true

# This file tells Bundler which Ruby gems this Jekyll site needs.
# A "gem" is a reusable Ruby package, similar to an npm package in JavaScript.

source "https://rubygems.org"

# Jekyll is the static site generator.
# Version 3.9.x matches the Jekyll generation used by GitHub Pages.
gem "jekyll", "~> 3.9.5"

# This lets Kramdown understand GitHub-Flavored Markdown details like fenced
# code blocks, while still supporting academic footnotes.
gem "kramdown-parser-gfm"

# The system Ruby on this machine is 2.6.10.
# Newer ffi releases require Ruby 3+, so this pin keeps installation compatible
# with the current local environment while still allowing Jekyll to run.
gem "ffi", "~> 1.15.5"

# Ruby 3 no longer ships WEBrick by default, and including it here also makes
# the project portable across newer Ruby installs.
gem "webrick"
