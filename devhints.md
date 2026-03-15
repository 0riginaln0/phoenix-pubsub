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

