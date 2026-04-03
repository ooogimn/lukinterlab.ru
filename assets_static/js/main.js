/*****************************************************************************
  ____                                  _____ _
 / ___|___  ___ _ __ ___   ___  ___    |_   _| |__   ___ _ __ ___   ___  ___
| |   / _ \/ __| '_ ` _ \ / _ \/ __|_____| | | '_ \ / _ \ '_ ` _ \ / _ \/ __|
| |__| (_) \__ \ | | | | | (_) \__ \_____| | | | | |  __/ | | | | |  __/\__ \
 \____\___/|___/_| |_| |_|\___/|___/     |_| |_| |_|\___|_| |_| |_|\___||___/

******************************************************************************/

/************ Site Main Js **************************************

    Template Name: Watson - Resume/Vcard Template
    Author: cosmos-themes
    Envato Profile: https://themeforest.net/user/cosmos-themes
    version: 1.0
    Copyright: 2018

****************************************************************/

/*======== Window Load Function ========*/
$(window).on('load', function() {

    /*======== Preloader ========*/
    $(".loader").fadeOut();
    $(".preloader").delay(1000).fadeOut();


    /*======== Isotope Portfolio Setup ========*/
    if( $('.portfolio-items').length ) {
        var $elements = $(".portfolio-items"),
            $filters = $('.portfolio-filter ul li');
        $elements.isotope();

        $filters.on('click', function(){
            $filters.removeClass('active');
            $(this).addClass('active');
            var selector = $(this).data('filter');
            $(".portfolio-items").isotope({
                filter: selector,
                hiddenStyle: {
                    transform: 'scale(.2) skew(30deg)',
                    opacity: 0
                },
                visibleStyle: {
                    transform: 'scale(1) skew(0deg)',
                    opacity: 1,
                },
                transitionDuration: '.5s'
            });
        });
    }

    /*======== Blogs Masonry Setup ========*/
    $('.blogs-masonry').isotope({ layoutMode: 'moduloColumns' });

});


/*======== Document Ready Function ========*/
$(document).ready(function() {

    "use strict";


    /*======== SimpleBar Setup ========*/
    $('.pt-page').each(function() {
        var $id = '#' + $(this).attr('id');
        new SimpleBar($($id)[0]);
    });

    /*======== Fitty Setup ========*/
    fitty('.header-name', {
        multiLine: false,
        maxSize: 20,
        minSize: 10
    });

    /*======== Active Current Link ========*/
    $('.nav-menu a').on('click',function() {
        if($('.header-content.on').length) {
            $('.header-content').removeClass('on');
        }
    });

    /*======== Mobile Toggle Click Setup ========*/
    $('.header-toggle').on('click', function() {
        $('header .header-content').toggleClass('on');
    });

    /*========Clients OwlCarousel Setup========*/
    $(".clients .owl-carousel").owlCarousel({
        loop: true,
        margin: 30,
        autoplay: true,
        smartSpeed: 500,
        responsiveClass: true,
        autoplayHoverPause: true,
        dots: false,
        responsive: {
            0: {
                items: 2,
            },
            500: {
                items: 3,
            },
            700: {
                items: 4,
            },
            1000: {
                items: 6,
            },
        },
    });

    /*========Testimonials OwlCarousel Setup========*/
    $(".testimonials .owl-carousel").owlCarousel({
        loop: true,
        margin: 30,
        autoplay: true,
        smartSpeed: 500,
        responsiveClass: true,
        dots: false,
        autoplayHoverPause: true,
        responsive: {
            0: {
                items: 1,
            },
            800: {
                items: 1,
            },
            1000: {
                items: 2,
            },
        },
    });

    /*======== Skills Progress Animation ========*/
    if($('.skills').length > 0) {

        var el = new SimpleBar($('#resume')[0]).getScrollElement();

        //When scrolled to Progress
        $(el).on('scroll', function() {
            animateProgress();
        });

        //When Resume Section have page-active on page load
        if($('#resume').hasClass('page-active')) {
            animateProgress();
        }

        //When Resume Link is clicked
        $('a[href="#resume"]').on('click', function(){
            animateProgress();
        });

        function animateProgress() {
            $('.progress .progress-bar').each(function() {
                var bottom_object = $(this).offset().top + $(this).outerHeight();
                var bottom_window = $(window).scrollTop() + $(window).height();
                var progressWidth = $(this).data('progress-value') + '%';
                if (bottom_window > bottom_object) {
                    $(this).css({
                        width: progressWidth
                    });
                    $(this).find('.progress-value').animate({
                        countNum: parseInt(progressWidth, 10)
                    }, {
                        duration: 2000,
                        easing: 'swing',
                        step: function() {
                            $(this).text(Math.floor(this.countNum) + '%');
                        },
                        complete: function() {
                            $(this).text(this.countNum + '%');
                        }
                    });
                }
            });
        }
    }

    /*======== Portfolio Image Link Setup ========*/
    $('.portfolio-items .image-link').magnificPopup({
        type: 'image',
        gallery: {
            enabled: true
        }
    });

    /*======== Portfolio Video Link Setup ========*/
    $('.portfolio-items .video-link').magnificPopup({
        type: 'iframe',
        gallery: {
            enabled: true
        }
    });

    /*======== Portfolio Ajax Link Setup ========*/
    ajaxPortfolioSetup($('.portfolio-items .ajax-link'), $('.ajax-portfolio-popup'));

    /*======== Portfolio Tilt Setup ========*/
    $('#portfolio .item figure').tilt({
        maxTilt: 3,
        glare: true,
        maxGlare: .6,
        reverse: true
    });

    /*======== Google Map Setup ========*/
    if($('#map').length) {
        initMap();
     }


    /*======== Contact Form Setup ========*/
    contactFormSetup();
});


/*********** Function Ajax Portfolio Setup **********/
function ajaxPortfolioSetup($ajaxLink, $ajaxContainer) {
    $ajaxLink.on('click', function(e) {
        var link = $(this).attr('href');

        if(link === "#") {
            e.preventDefault();
            return;
        }

        $ajaxContainer.find('.content-wrap .popup-content').empty();

        $ajaxContainer.addClass('on');
        $.ajax({
            url: link,
            beforeSend: function() {
                $ajaxContainer.find('.ajax-loader').show();
            },
            success: function(result) {
                $ajaxContainer.find('.content-wrap .popup-content').html(result);
            },
            complete: function() {
                $ajaxContainer.find('.ajax-loader').hide();
            },
            error: function(e) {
                $ajaxContainer.find('.ajax-loader').hide();
                $ajaxContainer.find('.content-wrap .popup-content').html('<h1 class="text-center">Something went wrong! Retry or refresh the page.</h1>')
            }
        });
        e.preventDefault();
    });

    $ajaxContainer.find('.popup-close').on('click', function() {
        $ajaxContainer.removeClass('on');
    });


}


/********** Function Map Initialization **********/
function initMap() {
    var latitude = $("#map").data('latitude'),
        longitude = $("#map").data('longitude'),
        zoom = $("#map").data('zoom'),
        cordinates = new google.maps.LatLng(latitude, longitude);

    var styles = [{"stylers":[{"saturation":-100},{"gamma":0.8},{"lightness":4},{"visibility":"on"}]},{"featureType":"landscape.natural","stylers":[{"visibility":"on"},{"color":"#5dff00"},{"gamma":4.97},{"lightness":-5},{"saturation":100}]}];
        var mapOptions = {
        zoom: zoom,
        center: cordinates,
        mapTypeControl: false,
        disableDefaultUI: true,
        zoomControl: true,
        scrollwheel: false,
        styles: styles
    };
    var map = new google.maps.Map(document.getElementById('map'), mapOptions);
    var marker = new google.maps.Marker({
        position: cordinates,
        map: map,
        title: "We are here!"
    });
}

/********** Function Contact Form Setup **********/
function contactFormSetup() {

    /*======== Check Field Have Value When Page Load ========*/
    $('.input__field').each(function() {
        if($(this).val()) {
            $(this).parent('.input').addClass('input--filled');
        } else {
            $(this).parent('.input').removeClass('input--filled');
        }
    });

    /*======== Check Field Have Value When Keyup ========*/
    $('.input__field').on('keyup', function() {
        if($(this).val()) {
            $(this).parent('.input').addClass('input--filled');
        } else {
            $(this).parent('.input').removeClass('input--filled');
        }
    });


    $('#contact-form').on('submit', function(e) {
        e.preventDefault();
        var name = $('#cf-name').val(),
            email = $('#cf-email').val(),
            message = $('#cf-message').val(),
            $messageBox = $('#contact-form .message'),
            required = 0;
        
        console.log('Отправляем данные:', { name: name, email: email, message: message });


        $('.cf-validate', this).each(function() {
            if($(this).val() == '') {
                $(this).addClass('cf-error');
                required += 1;
            } else {
                if($(this).hasClass('cf-error')) {
                    $(this).removeClass('cf-error');
                    if(required > 0) {
                        required -= 1;
                    }
                }
            }
        });
        if( required === 0 ) {
            // Получаем CSRF токен
            var csrfToken = $('[name=csrfmiddlewaretoken]').val();
            var $submitBtn = $('#cf-submit');
            
            // Создаем FormData для поддержки файлов
            var formData = new FormData();
            formData.append('name', name);
            formData.append('email', email);
            formData.append('message', message);
            formData.append('csrfmiddlewaretoken', csrfToken);
            
            // Добавляем файл, если выбран
            var attachment = $('#attachment')[0].files[0];
            if (attachment) {
                // Проверяем размер файла (5MB)
                if (attachment.size > 5 * 1024 * 1024) {
                    showAlertBox(400, 'Размер файла не должен превышать 5MB.');
                    return;
                }
                formData.append('attachment', attachment);
            }
            
            // Показываем индикатор загрузки
            $submitBtn.addClass('loading').prop('disabled', true);
            
            $.ajax({
                type: 'POST',
                url: '/contact/',
                data: formData,
                processData: false,
                contentType: false,
                dataType: "json",
                success: function(data) {
                    console.log(data);
                    showAlertBox(data.status, data.message);
                },
                error: function(xhr, status, error) {
                    console.error('AJAX Error:', status, error);
                    showAlertBox(500, 'Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.');
                },
                complete: function() {
                    // Убираем индикатор загрузки
                    $submitBtn.removeClass('loading').prop('disabled', false);
                }
            });
        }
    });
}


/********** Function Show Alert Box **********/
function showAlertBox(response, message) {
    var $alContainer = $('#contact-form .alert-container');
    
    // Очищаем предыдущие уведомления
    $alContainer.empty().show();
    
    if( response == 200 ) {
        // Создаем красивое уведомление об успехе
        var successHTML = `
            <div class="alert alert-success">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-green-800">${message}</p>
                    </div>
                </div>
            </div>
        `;
        $alContainer.html(successHTML);
        
        // Очищаем форму только при успешной отправке
        $("#contact-form")[0].reset();
        $("#contact-form .input").removeClass('input--filled');
        
        // Добавляем визуальный эффект успеха
        $("#contact-form").addClass('success');
        setTimeout(function() {
            $("#contact-form").removeClass('success');
        }, 3000);
        
        // Показываем модальное окно, если оно существует
        if ($('#contact-success-modal').length > 0) {
            $('#contact-success-modal').removeClass('hidden').fadeIn(300);
        }
    } else {
        // Создаем уведомление об ошибке
        var errorHTML = `
            <div class="alert alert-danger">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-red-800">${message}</p>
                    </div>
                </div>
            </div>
        `;
        $alContainer.html(errorHTML);
    }
    
    // Анимация появления
    $alContainer.children().hide().fadeIn(300);
    
    // Прокручиваем к форме, чтобы было видно уведомление
    var formTop = $("#contact-form").offset().top - 100;
    if ($(window).scrollTop() > formTop) {
        $('html, body').animate({
            scrollTop: formTop
        }, 500);
    }
    
    // Автоматически скрываем через 7 секунд
    setTimeout(function() {
        $alContainer.fadeOut(400, function() {
            $(this).empty();
        });
    }, 7000);
}

