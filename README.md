# Rohit Naidu Research Blog

A Jekyll research blog with a retro academic style: serif typography, cream
background, footnotes, sidenotes, and plain old-web links.

## How the site works

Jekyll is a static site generator. That means:

- You write pages and articles as HTML or Markdown.
- Jekyll converts them into static HTML files.
- GitHub Pages can host those files for free.
- There is no backend, database, login system, or JavaScript requirement.

## Run locally

From this folder:

```sh
bundle install
bundle exec jekyll serve
```

Then open:

```text
http://127.0.0.1:4000
```

## Important files

- `_config.yml` controls site-wide settings like the title, author, and social links.
- `index.html` is the homepage.
- `_posts/` contains article Markdown files.
- `_layouts/default.html` is the shared page shell.
- `_layouts/post.html` controls article pages.
- `_includes/` contains reusable HTML pieces.
- `assets/css/style.css` controls the retro academic look.

## Add a new article

Create a new file in `_posts/` using this naming format:

```text
YYYY-MM-DD-title-of-article.md
```

Example:

```text
_posts/2026-05-23-mechanisms-of-nausea.md
```

Start the file with front matter:

```md
---
layout: post
title: "Mechanisms of Nausea"
description: "Short summary for search engines and link previews."
---

## First Section

Write the article here.
```

Jekyll automatically adds the post to the Articles list on the homepage.

## Footnotes

Kramdown supports academic-style footnotes:

```md
This sentence has a citation.[^paper]

[^paper]: Add the paper, note, or citation details here.
```

## Sidenotes

Use a sidenote when a comment is useful but should not interrupt the main text:

```html
<aside class="sidenote">
  This appears in the right margin on wide screens.
</aside>
```

## Update social links

Edit `_config.yml`:

```yml
social:
  linkedin: "https://www.linkedin.com/in/YOUR-LINKEDIN"
  github: "https://github.com/YOUR-GITHUB"
  devpost: "https://devpost.com/YOUR-DEVPOST"
```

## Deploy with GitHub Pages

1. Create a GitHub repository.
2. Push this folder to the repository.
3. In GitHub, go to `Settings -> Pages`.
4. Choose the branch you want to deploy, usually `main`.
5. If this is a project site, update `_config.yml`:

```yml
url: "https://YOUR_GITHUB_USERNAME.github.io"
baseurl: "/REPOSITORY_NAME"
```

If this is a user site named `YOUR_GITHUB_USERNAME.github.io`, keep:

```yml
baseurl: ""
```
