var g = jQuery;

var config = {
    "issuesAjaxUrl":"/hz/vendor/members/contact/ajax/issues",
    "siteArea":"MEMBERS",
    "fileTypeList":["bmp","csv","doc","docx","gif","htm","html","jpg","jpeg","pdf","png","rtf","tif","tiff","txt","xls","xlsx","xml","zip"],
    "recentAsinsAjaxUrl":"/hz/vendor/members/contact/ajax/search/recentCatalogItems",
    "businessGroups":[
    {"displayName":"Pantry","businessGroupId":776,"name":"US Pantry"},
    {"displayName":"Amazon Fresh","businessGroupId":257,"name":"US Amazon Fresh"},
    {"displayName":"Sporting Goods","businessGroupId":178,"name":"US Sporting Goods"},
    {"displayName":"Grocery & Gourmet Food","businessGroupId":232,"name":"US Grocery"}],
    "fileSizeLimit":4,
    "fileCountLimit":4,
    "emailFormAjaxUrl":"/hz/vendor/members/contact/ajax/emailform"
}

function getBusinessGroups() {
    return config.businessGroups
}

var c = {
    MEMBERS: "MEMBERS",
    PUBLIC: "PUBLIC",
    SETUP: "SETUP",
    REGISTRATION: "REGISTRATION"
}
, b = {
    BUSINESS_GROUP: "BUSINESS_GROUP",
    ISSUE_LIST: "ISSUE_LIST",
    ISSUE_SELECT_MEDIUM: "ISSUE_SELECT_MEDIUM",
    ISSUE_EMAIL_SUBMISSION: "ISSUE_EMAIL_SUBMISSION",
    ISSUE_PHONE_SUBMISSION: "ISSUE_PHONE_SUBMISSION",
    ISSUE_EMAIL_CONFIRMATION: "ISSUE_EMAIL_CONFIRMATION",
    ERROR: "ERROR"
}
  , viewState = null 
  , selectedBusinessGroup = null 
  , issue = null 
  , m = null ;

(function(siteArea) {
    viewState = c.MEMBERS === siteArea ? b.BUSINESS_GROUP : c.PUBLIC === siteArea ? b.ISSUE_LIST : b.ERROR
})(config.siteArea); // e = "MEMBERS"

console.log(viewState);

var predefinedFunctions = {
    getSiteArea: function() {
        return config.siteArea
    },
    getCurrentViewState: function() {
        return viewState
    },
    setCurrentViewState: function(newViewState) {
        // if (viewState !== newViewState) {
        //     if (!b[newViewState])
        //         throw "Invalid view state " + newViewState;
        //     var oldViewState = viewState;
        //     viewState = newViewState;
        //     // g.trigger("vss-contact-on-view-change", viewState, oldViewState)
        // }

        if (newViewState === b.ISSUE_EMAIL_CONFIRMATION) {
            $("#vss-contact-email-confirmation-section").removeClass("aok-hidden");
        } else if (newViewState === b.ERROR) {
            $("#vss-contact-error-message-section").removeClass("aok-hidden");
        }
    },
    registerViewStateChangeListener: function(cb) {
        if ("function" !== typeof cb)
            throw cb + " is not a function";
        // g.on("vss-contact-on-view-change", cb)
    },
    getBusinessGroups: getBusinessGroups,
    getSelectedBusinessGroup: function() {
        return selectedBusinessGroup
    },
    setSelectedBusinessGroup: function(bg) {
        selectedBusinessGroup = bg
    },
    allowChangeBusinessGroups: function() {
        var businessGroups = getBusinessGroups();
        return businessGroups && 1 !== businessGroups.length ? !0 : !1
    },
    getIssuesAjaxUrl: function() {
        return config.issuesAjaxUrl
    },
    getSelectedIssue: function() {
        return issueId
    },
    setSelectedIssue: function(newIssue) {
        if (!issue || newIssue.issue.issueId !== issue.issue.issueId) {
            var oldIssue = issue;
            issue = newIssue;
            // g.trigger("vss-contact-on-selected-issue-change", issue, oldIssue)
        }
    },
    getEmailFormAjaxUrl: function() {
        return config.emailFormAjaxUrl
    },
    registerSelectedIssueChangeListener: function(cb) {
        if ("function" !== typeof cb)
            throw cb + " is not a function";
        // g.on("vss-contact-on-selected-issue-change", cb)
    },
    getFileSizeLimit: function() {
        return config.fileSizeLimit
    },
    getFileCountLimit: function() {
        return config.fileCountLimit
    },
    getFileTypeList: function() {
        return config.fileTypeList
    },
    getRecentAsinsAjaxUrl: function() {
        return config.recentAsinsAjaxUrl
    },
    getEmailSubmissionCcList: function() {
        return m
    },
    setEmailSubmissionCcList: function(a) {
        m = a
    },
    VIEW_STATE: b,
    SITE_AREA: c
}

var init = function (pageManager, attachmentManager, formManager) {
    var l = $("#vss-contact-email-submission-section")
      , formPostIframe = $("#vss-contact-form-post-iframe")
      , u = $("#vss-contact-generate-email-form-csrf-section").find('[name="csrfToken"]').val()
      , q = $("#vss-contact-email-form-section")
      , r = $("#vss-contact-email-form-loading-spinner");

    $('#details').val('For help with you product detail page or buy button issues, provide the following:\n\n' +

    '•  ASINs (required):\n' +
    '•  Describe the issue (required): \n\n' +

    'Did you know?  \n' +
    'Products are only searchable if there is inventory or demand for that product. To update your search keywords, use the Item Maintenance Form template in the Selling your Products section of the Resource Center to organize this data. '
    );

    formManager.init();
    attachmentManager.initAttachments();

    $("#" + formManager.getFormId()).submit(function() {
        $("#vss-contact-loading-mask").removeClass('aok-hidden');
    })

    formPostIframe.on('load', function () {
        $("#vss-contact-loading-mask").addClass('aok-hidden');
        var content = formPostIframe.contents() , result = content.find("#status").html();
        console.log('[upload - response] - ', $(this).contents().text());

        if (result === "OK") {
            pageManager.setEmailSubmissionCcList(content.find("#ccList").html())

            pageManager.setCurrentViewState(pageManager.VIEW_STATE.ISSUE_EMAIL_CONFIRMATION)

        } else if (result === "Bad Request") {
            var errorCode = content.find("#errorCode").html();
            if (errorCode == "FILE_TYPE_NOT_SUPPORTED") {
                attachmentManager.showAttachmentTypeError()
            } else if (errorCode == "FILE_SIZE_EXCEEDED") {
                attachmentManager.showAttachmentSizeError()
            } else {
                pageManager.setCurrentViewState(pageManager.VIEW_STATE.ERROR)
            }
        } else {
            pageManager.setCurrentViewState(pageManager.VIEW_STATE.ERROR)
        }
    });
}

var init_form = function (a) {
    function c(a) {
        a = $("#" + formID).find('[name="' + a + '"]');
        var b = [];
        $.each(a, function(a, c) {
            var d = $.trim($(c).val());
            "" !== d && b.push(d)
        });
        return b
    }
    function showWarning(a) {
        $.each(formFieldData, function(b, d) {
            if (d.id === a)
                return !1;
            0 === c(d.id).length && $("#vss-contact-email-form-warning-" + d.id).removeClass("aok-hidden")
        })
    }
    function e(a) {
        var c = $("#" + a.id)
          , e = $("<ul></ul>");
        c.after(e);
        c.remove();
        var c = a.properties
          , f = {
            fieldName: a.id,
            autocomplete: {
                source: []
            },
            autocompleteOptionFormat: function(a, b) {
                return '<span class="vss-contact-suggestion-highlight">' + 
                b + "</span>" + a.substring(b.length)
            },
            allowSpaces: !0,
            allowDuplicates: !0,
            gridUnits: 12,
            rows: 3,
            autocompleteHeaderText: c.suggestionHeader,
            onFocus: function() {
                showWarning(a.id)
            }
        };
        null  !== a.placeholder && (f.placeholder = a.placeholder,
        f.textInputCssWidthPropertyWithPlaceholder = "480px");
        // e.tagit(f);
        // "asin" === c.suggestionType && d.getRecentAsinsAsync(function(a) {
        //     var b = [];
        //     $.each(a, function(a, c) {
        //         b.push({
        //             label: c.asin + " " + c.title,
        //             value: c.asin
        //         })
        //     });
        //     e.tagit("setAutocompleteSource", b)
        // })
    }
    function k(a) {
        $("#" + a.id).focus(function() {
            showWarning(a.id)
        })
    }
    function h(idx, field) {
        var warningContent = field.properties.warning;
        if (warningContent) {
            var el = $("#" + field.id + "-wrap")
              , elWarning = warningTemplate.clone();
            elWarning.attr("id", "vss-contact-email-form-warning-" + field.id);
            elWarning.find(".a-alert-content").html(warningContent);
            el.append(elWarning)
        }
        field.properties.taggable ? e(field) : k(field)
    }
    var formID, formFieldData, warningTemplate = $(".vss-contact-email-warning-template");
    return {
        init: function() {
            formID = $(".vss-contact-email-form").attr("id");
            var a = $("#" + formID + "-harmonic-fields-data").text();
            formFieldData = JSON.parse(a);
            $.each(formFieldData, h)
        },
        getFormId: function() {
            return formID
        },
        showWarningForAllFields: function() {
            showWarning()
        }
    }
}

var init_vss_contact_email_attachment = function(g, a) {
    function d() {
        h.show()
    }
    function c() {
        f.show()
    }
    var b = g, e, k, h, m, f, l;
    return {
        initAttachments: function() {
            function g(a) {
                var c = !1;
                l.find(".vss-contact-attachment-content").each(function() {
                    var d = b(this)
                      , e = d.find(".vss-contact-attachment-file");
                    if (e[0] && e[0].files[0] && 0 !== e[0].files[0].length && d.find(".vss-contact-attachment-name").text() === a)
                        return c = !0,
                        !1
                });
                return c
            }
            function n(a) {
                a[0].value = "";
                a.closest(".vss-contact-attachment-content").find(".vss-contact-attachment-name").text("")
            }
            function q(a) {
                return a.name + ' <span class="vss-contact-gray-text">(' + (parseFloat(a.size) / 1048576).toFixed(2) + " MB)</span>"
            }
            function r() {
                var c = 0;
                l.find(".vss-contact-attachment-content").each(function() {
                    var a = b(this)
                      , d = a.find(".vss-contact-attachment-file");
                    d[0] && d[0].files[0] && 0 !== d[0].files[0].length ? d[0] && d[0].files[0] && (a.find(".vss-contact-attachment-name").html(q(d[0].files[0])),
                    a.show(),
                    c++) : a.hide()
                });
                c >= a.getFileCountLimit() ? e.hide() : (0 < c ? k.hide() : k.show(),
                e.show())
            }
            e = b("#vss-contact-add-attachment-button");
            b("#vss-contact-add-attachment");
            k = b("#vss-contact-no-selected-file-label");
            h = b("#vss-contact-file-size-error");
            m = b("#vss-contact-file-name-error");
            f = b("#vss-contact-file-type-error");
            l = b("#vss-contact-attachment-content-list");
            b(".vss-contact-remove-attachment").click(function(a) {
                a.preventDefault();
                a = b(a.target).closest(".vss-contact-attachment-content");
                var c = a.find(".vss-contact-attachment-file");
                n(c);
                a.appendTo(l);
                r()
            });
            b(".vss-contact-attachment-file").change(function() {
                var e = b(this);
                if (e[0] && e[0].files && 0 < e[0].files.length && e[0] && e[0].files[0]) {
                    var k = e[0].files[0], l = (parseFloat(k.size) / 1048576).toFixed(2), k = k.name, p;
                    p = k.split(".");
                    if (2 > p.length)
                        p = !0;
                    else {
                        p = p.pop();
                        var q = a.getFileTypeList();
                        p = "undefined" === typeof q || 0 === q.length ? !1 : 0 > q.indexOf(p.toLowerCase())
                    }
                    p ? (c(),
                    h.hide(),
                    m.hide(),
                    n(e)) : 
                    l > a.getFileSizeLimit() ? (d(),
                    m.hide(),
                    f.hide(),
                    n(e)) : g(k) ? (m.show(),
                    h.hide(),
                    f.hide(),
                    n(e)) : (h.hide(),
                    m.hide(),
                    f.hide())
                }
                r()
            });
            e.click(function(a) {
                a.preventDefault();
                var c = 0;
                l.find(".vss-contact-attachment-content").each(function() {
                    var a = b(this).find(".vss-contact-attachment-file");
                    if (a[0] && a[0].files && 0 === a[0].files.length)
                        return a.click(),
                        !1;
                    c++
                })
            });
            h.hide();
            m.hide();
            f.hide();
            r()
        },
        showAttachmentTypeError: c,
        showAttachmentSizeError: d
    }
};

init( predefinedFunctions,
     init_vss_contact_email_attachment(g, predefinedFunctions), 
     init_form(predefinedFunctions)
     );
