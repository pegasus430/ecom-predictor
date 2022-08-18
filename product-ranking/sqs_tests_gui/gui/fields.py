from django import forms


class CustomSelectWidget(forms.Widget):
    def __init__(self, choices, width=300, *args, **kwargs):
        self.choices = choices
        self.width = width
        super(CustomSelectWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        template = """
        <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.2.0/jquery.min.js"></script>"
        <link rel="stylesheet" href="https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.4/themes/smoothness/jquery-ui.css">
        <script src="https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.4/jquery-ui.min.js"></script>

        <input type='text' id='id_%s' name='%s' value='%s' style='width:%spx'/>

        <script>
            var tags = [%s];
            $( "#id_spider" ).autocomplete({
              source: function( request, response ) {
                      var matcher = new RegExp( "^" + $.ui.autocomplete.escapeRegex( request.term ), "i" );
                      response( $.grep( tags, function( item ){
                          return matcher.test( item );
                      }) );
                  }
            });
        </script>
        """
        rendered_choices = ""
        for choice in self.choices:
            rendered_choices += '"%s",' % choice[0]
        rendered_choices = rendered_choices.rstrip(',')
        if not value:
            value = ''
        return template % (name, name, value, self.width, rendered_choices)
