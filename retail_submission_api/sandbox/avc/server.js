/*Define dependencies.*/

var express=require("express");
var multer  = require('multer');
var path = require('path');
var fs = require('fs');
var morgan = require('morgan')
var FileStreamRotator = require('file-stream-rotator')
var bodyParser = require('body-parser')
var moment = require('moment')

var logDirectory = __dirname + '/log'

var app=express();
var upload = multer({ dest: 'uploads/' });

// ensure log directory exists 
fs.existsSync(logDirectory) || fs.mkdirSync(logDirectory)

// create a rotating write stream 
var accessLogStream = FileStreamRotator.getStream({
  date_format: 'YYYYMMDD',
  filename: logDirectory + '/access-%DATE%.log',
  frequency: 'daily',
  verbose: false
})

/* Setting up middlewars */
app.use(bodyParser.urlencoded({ extended: false }))
app.use(bodyParser.json())
app.use(morgan('combined', {stream: accessLogStream}))

app.use('/assets', express.static('assets'));


/*Handling routes.*/
app.get('/',function(req,res){
    res.sendFile(path.join(__dirname + '/index.html'));
});

app.get('/arap',function(req,res){
    res.redirect('/gp/vendor/sign-in?return_to=arap');
});

app.get('/arap/dashboard/snapshot',function(req,res){
    res.sendFile(path.join(__dirname + '/arap/snapshot.html'));
});

app.get('/arap/dashboard/salesDiagnostic',function(req,res){
    res.sendFile(path.join(__dirname + '/arap/sales_diagnostic.html'));
});

app.get('/arap/Sales%20Diagnostic_Detail%20View_US.csv',function(req,res){
    res.sendFile(path.join(__dirname + '/arap/sales_diagnostic.csv'));
});

app.get('/arap/dashboard/searchTerms',function(req,res){
    var department = req.query.department || '';
    if (department) {
        department = '-' + department;
    }
    var range = req.query.range || '';
    if (range) {
        range = '-' + range;
    }
    res.sendFile(path.join(__dirname + '/arap/search_terms' + department + range + '.html'));
});

app.get('/gp/vendor/sign-in',function(req,res){
    res.sendFile(path.join(__dirname + '/index.html'));
});

app.get('/failure',function(req,res){
    res.sendFile(path.join(__dirname + '/failure.html'));
});

app.get('/ap/mfa',function(req,res){
    if (req.query.failure) {
        res.sendFile(path.join(__dirname + '/mfa_failure.html'));
    }
    else {
        res.sendFile(path.join(__dirname + '/mfa.html'));
    }
});

app.get('/st/vendor/members/dashboard',function(req,res){
    res.sendFile(path.join(__dirname + '/dashboard.html'));
});

app.get('/gp/vendor/members/dashboard',function(req,res){
    res.redirect('/st/vendor/members/dashboard');
});

app.get('/gp/vendor/members/image-upload',function(req,res){
    res.sendFile(path.join(__dirname + '/image_upload.html'));
});

app.post('/gp/vendor/members/image-upload',function(req,res){
    res.redirect('/gp/vendor/members/image-upload?status=ok');
});

app.get('/upload',function(req,res){
    res.sendFile(path.join(__dirname + '/upload.html'));
});

app.get('/status',function(req,res){
    res.sendFile(path.join(__dirname + '/status.html'));
});

app.get('/st/vendor/members/contactusapp',function(req,res){
    res.sendFile(path.join(__dirname + '/contactus.html'));
});

app.get('/st/vendor/members/analytics/basic/dashboard',function(req,res){
    res.sendFile(path.join(__dirname + '/analytics.html'));
});

app.get('/st/vendor/members/analytics/basic/productDetail',function(req,res){
    res.sendFile(path.join(__dirname + '/product_detail.html'));
});

app.get('/dashboard.csv',function(req,res){
    res.sendFile(path.join(__dirname + '/dashboard.csv'));
});

app.get('/image-upload.csv',function(req,res){
    res.sendFile(path.join(__dirname + '/image-upload.csv'));
});

app.get('/ProductDetails.csv',function(req,res){
    res.sendFile(path.join(__dirname + '/ProductDetails.csv'));
});

app.get('/hz/vendor/members/contact',function(req,res){
    res.sendFile(path.join(__dirname + '/upload_contact_email.html'));
});

app.get('/gp/vendor/members/caselog/open-resolved',function(req,res){
    res.sendFile(path.join(__dirname + '/open_cases.html'));
});

app.get('/hz/vendor/members/products/mycatalog/ajax/query',function(req,res){
    var offset = req.query.offset || '';
    res.sendFile(path.join(__dirname + '/image_catalog' + offset + '.html'));
});

app.get('/hz/vendor/members/products/images/manage',function(req,res){
    res.sendFile(path.join(__dirname + '/image_catalog/images-' + req.query.products + '.html'));
});

app.get('/hz/vendor/members/products/mycatalog/ajax/query',function(req,res){
    res.sendFile(path.join(__dirname + '/query.html'));
});


var cpUpload = upload.fields([{ name: 'attachments', maxCount: 4 }]);

app.post('/hz/vendor/members/contact/ajax/email/create', cpUpload, function(req,res) {
    // console.log(req.body);
    accessLogStream.write('\n---- text file uploaded ----\n');
    accessLogStream.write(JSON.stringify(req.body, null, '  '));
    accessLogStream.write(JSON.stringify(req.files, null, '  '));
    accessLogStream.write('\n--------------------------\n');
    if (req.files && req.files.attachments && req.files.attachments.length > 0) {
        res.send('<div id="status">OK</div><div id="ccList">mocklist</div>');
    } else {
        res.send('<div id="status">Bad Request</div><div id="errorCode">ERROR</div>');
    }
});

app.get('/view-history', function (req, res) {
    var date = moment().format('YYYYMMDD')
    var file = logDirectory + '/access-' + date + '.log';
    fs.readFile(file, 'utf8',function (err, data) {
        if (err) {
            res.send('Could not open today\'s log file.');
        } else {
            res.send('<pre>' + data + '</pre><p><a href="/">Back</a></p>');
        }
    });
});

/*Run the server.*/
app.listen(8889,function(){
    console.log("Working on port 8889");
});