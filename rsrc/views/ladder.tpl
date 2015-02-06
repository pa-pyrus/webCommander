<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <link rel="shortcut icon" href="/static/favicon.ico">
    <title>UberSkill Ladder</title>
  </head>
  <body>
    <h1>UberSkill Ladder</h1>
    <ol>
% for name in top:
      <li>{{name}}</li>
% end
    </ol>

    <h2>Disclaimer</h2>
    <p><small>
      This ranking is calculated using the <a href="https://raw.githubusercontent.com/sublee/trueskill/master/LICENSE">BSD-licensed</a> <a href="http://trueskill.org/">TrueSkill</a> package.
      The algorithm itself it patented and the <strong>TrueSkill&trade;</strong> brand is trademarked, both by <em>Microsoft Corporation</em>.
    </small></p>
  </body>
</html>
