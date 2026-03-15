Generate docs:

`uvx pdoc src/phoenix_pubsub/ -o ./docs --docformat google`

replace
```html
    <style>/*! syntax-highlighting.css */
    <style>/*! theme.css */
```

with
```html
<!-- Dark theme styles -->
<link rel="stylesheet" href="theme.css" media="(prefers-color-scheme: dark)">
<link rel="stylesheet" href="syntax-highlighting.css" media="(prefers-color-scheme: dark)">

<!-- Light theme styles -->
<link rel="stylesheet" href="theme-light.css" media="(prefers-color-scheme: light)">
<link rel="stylesheet" href="syntax-highlighting-light.css" media="(prefers-color-scheme: light)">
```

Publishing new release:

```sh
uv version --bump <major or minor or patch>
uv build
git add .
git commit -m "new version"
git tag v0.6.0
git push origin v0.6.0
git push
```
