//set up hapijs server
var Hapi = require('hapi');
var async = require('async');
var fs = require('fs');

var server = new Hapi.Server();
server.connection({ port: 8888, host: '0.0.0.0' });

//set up inert for static files
server.register(require('inert'), (err) => {
    if (err) {
        throw err;
    }
});

server.route({  
  method: 'GET',
  path: '/assets/{file*}',
  handler: {
    directory: { 
      path: 'assets'
    }
  }
})

//server routes
server.route({
    method: 'GET',
    path: '/',
    handler: function (request, reply) {
        reply.file('index.html');
    }
});
server.route({
    method: 'GET',
    path: '/gp/vendor/sign-in',
    handler: function (request, reply) {
        reply.file('index.html');
    }
});
server.route({
    method: 'GET',
    path: '/failure',
    handler: function (request, reply) {
        reply.file('failure.html');
    }
});
server.route({
    method: 'GET',
    path: '/st/vendor/members/dashboard',
    handler: function (request, reply) {
        reply.file('dashboard.html');
    }
});
server.route({
    method: 'GET',
    path: '/gp/vendor/members/image-upload',
    handler: function (request, reply) {
        reply.file('image_upload.html');
    }
});
server.route({
    method: 'POST',
    path: '/gp/vendor/members/image-upload',
        handler: function (request, reply) {
        reply.redirect('/gp/vendor/members/image-upload?status=ok');
    }
});
server.route({
    method: 'GET',
    path: '/upload',
    handler: function (request, reply) {
        reply.file('upload.html');
    }
});
server.route({
    method: 'GET',
    path: '/status',
    handler: function (request, reply) {
        reply.file('status.html');
    }
});
server.route({
    method: 'GET',
    path: '/st/vendor/members/contactusapp',
    handler: function (request, reply) {
        reply.file('contactus.html');
    }
});
server.route({
    method: 'GET',
    path: '/st/vendor/members/analytics/basic/dashboard',
    handler: function (request, reply) {
        reply.file('analytics.html');
    }
});
server.route({
    method: 'GET',
    path: '/st/vendor/members/analytics/basic/productDetail',
    handler: function (request, reply) {
        reply.file('product_detail.html');
    }
});
server.route({
    method: 'GET',
    path: '/dashboard.csv',
    handler: function (request, reply) {
        reply.file('dashboard.csv');
    }
});
server.route({
    method: 'GET',
    path: '/image-upload.csv',
    handler: function (request, reply) {
        reply.file('image-upload.csv');
    }
});

server.route({
    method: 'GET',
    path: '/ProductDetails.csv',
    handler: function (request, reply) {
        reply.file('ProductDetails.csv');
    }
});

server.route({
    method: 'GET',
    path: '/hz/vendor/members/contact',
    handler: function (request, reply) {
        reply.file('upload_contact_email.html');
    }
});

server.route({
    method: 'POST',
    path: '/hz/vendor/members/contact/ajax/email/create',
    config: {

        payload: {
            output: 'stream',
            parse: true,
            allow: 'multipart/form-data'
        },

        handler: function (request, reply) {
            console.log('log: /hz/vendor/members/contact/ajax/email/create');
            var data = request.payload;
            if (data.attachments && data.attachments.length > 0) {
                if (data.attachments[0].hapi.filename === "") {
                    console.log("attachments Does not Exsit");
                    var ret = '<div id="status">Bad Request</div>'
                            + '<div id="errorCode">ERROR</div>';
                    reply(ret);
                } else {
                    async.each(data.attachments, function(fileData, callback) {
                        if (fileData.hapi.filename === "") {
                            callback();
                            return;
                        }
                        var name = fileData.hapi.filename;
                        var path = __dirname + "/uploads/" + name;
                        var file = fs.createWriteStream(path);

                        file.on('error', function (err) { 
                            console.log("file write error", err);
                        });

                        fileData.pipe(file);

                        fileData.on('end', function (err) { 
                            var ret = {
                                filename: fileData.hapi.filename,
                                headers: fileData.hapi.headers
                            }
                            callback(err);
                        })
                    }, function(err) {
                        if( err ) {
                            console.log('Upload failure', err);
                            // var ret = {
                            //     success: false,
                            //     error: err
                            // }
                            var ret = '<div id="status">Bad Request</div>'
                            + '<div id="errorCode">' + err + '</div>';
                            reply(ret);
                        } else {
                            console.log('Upload success');
                            // var ret = {
                            //     filename: data.attachments[0].hapi.filename,
                            //     headers: data.attachments[0].hapi.headers
                            // }
                            var ret = '<div id="status">OK</div>'
                            + '<div id="ccList">mocklist</div>';
                            reply(ret);
                        }
                    });
                }
            }

        }
    }
});
//start hapi server
server.start(function () {
    console.log('Server running at:', server.info.uri);
});
