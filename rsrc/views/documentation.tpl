<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <link rel="shortcut icon" href="/static/favicon.ico">
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="//code.jquery.com/ui/1.11.2/themes/pepper-grinder/jquery-ui.css">
    <script src="//code.jquery.com/jquery-2.1.1.min.js"></script>
    <script src="//code.jquery.com/ui/1.11.2/jquery-ui.min.js"></script>
    <script>
    $(function() {
      $( "#accordion" ).accordion({
        collapsible: true, active: false, heightStyle: "content"
      });
    });
    </script>
    <title>REST API Documentation</title>
  </head>
  <body>
    <div id="header">
      <h1>REST API Documentation</h1>
    </div>

    <div id="accordion">
% for doc in documentation:
      <h1>{{doc["title"]}}</h1>
      <div>
{{!doc["content"]}}
      </div>
% end
    </div>
  </body>
</html>
