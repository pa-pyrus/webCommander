<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>PA Leaderboards</title>
    <link rel="shortcut icon" href="/static/favicon.ico">
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="//code.jquery.com/ui/1.11.2/themes/pepper-grinder/jquery-ui.css">
    <script src="//code.jquery.com/jquery-2.1.1.min.js"></script>
    <script src="//code.jquery.com/ui/1.11.2/jquery-ui.min.js"></script>
    <script>
      $(function() {
        $( "#tabs" ).tabs();
      });
    </script>
  </head>
  <body>
    <h1>PA Leaderboards</h1>
    <div id="tabs">
      <ul>
        <li><a href="#tabs-uber">Uber League</a></li>
        <li><a href="#tabs-platinum">Platinum League</a></li>
        <li><a href="#tabs-gold">Gold League</a></li>
        <li><a href="#tabs-silver">Silver League</a></li>
        <li><a href="#tabs-bronze">Bronze League</a></li>
      </ul>
      <div id="tabs-uber">
        <ol>
% for name in leaderboards["Uber"]:
          <li>{{name}}</li>
% end
        </ol>
      </div>
      <div id="tabs-platinum">
        <ol>
% for name in leaderboards["Platinum"]:
          <li>{{name}}</li>
% end
        </ol>
      </div>
      <div id="tabs-gold">
        <ol>
% for name in leaderboards["Gold"]:
          <li>{{name}}</li>
% end
        </ol>
      </div>
      <div id="tabs-silver">
        <ol>
% for name in leaderboards["Silver"]:
          <li>{{name}}</li>
% end
        </ol>
      </div>
      <div id="tabs-bronze">
        <ol>
% for name in leaderboards["Bronze"]:
          <li>{{name}}</li>
% end
        </ol>
      </div>
    </div>
  </body>
</html>
