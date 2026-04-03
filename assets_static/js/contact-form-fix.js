// Исправление для контактной формы
(function() {
    'use strict';
    
    // Ждем полной загрузки DOM и jQuery
    function initContactForm() {
        var form = document.getElementById('contact-form');
        if (!form) {
            console.error('Contact form not found');
            return;
        }
        
        // Убеждаемся, что jQuery загружен
        if (typeof jQuery === 'undefined') {
            console.error('jQuery not loaded');
            return;
        }
        
        console.log('Initializing contact form AJAX handler');
        
        // Удаляем старые обработчики
        jQuery(form).off('submit');
        
        // Добавляем новый обработчик
        jQuery(form).on('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Form submitted via AJAX');
            
            var $form = jQuery(this);
            var $submitBtn = $form.find('#cf-submit');
            var $alertContainer = $form.find('.alert-container');
            
            // Собираем данные
            var formData = new FormData(this);
            
            // Показываем индикатор загрузки
            $submitBtn.prop('disabled', true).addClass('loading');
            
            // Очищаем предыдущие сообщения
            $alertContainer.empty();
            
            // Отправляем AJAX запрос
            jQuery.ajax({
                url: $form.attr('action'),
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                dataType: 'json',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function(response) {
                    console.log('Success:', response);
                    
                    // Показываем сообщение об успехе
                    var alertHtml = '<div class="alert alert-success">' +
                        '<i class="fas fa-check-circle mr-2"></i>' +
                        response.message +
                        '</div>';
                    
                    $alertContainer.html(alertHtml).fadeIn();
                    
                    // Очищаем форму
                    form.reset();
                    
                    // Прокручиваем к сообщению
                    jQuery('html, body').animate({
                        scrollTop: $alertContainer.offset().top - 100
                    }, 500);
                    
                    // Скрываем сообщение через 5 секунд
                    setTimeout(function() {
                        $alertContainer.fadeOut();
                    }, 5000);
                },
                error: function(xhr, status, error) {
                    console.error('Error:', status, error);
                    
                    var message = 'Произошла ошибка при отправке сообщения.';
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        message = xhr.responseJSON.message;
                    }
                    
                    // Показываем сообщение об ошибке
                    var alertHtml = '<div class="alert alert-danger">' +
                        '<i class="fas fa-exclamation-circle mr-2"></i>' +
                        message +
                        '</div>';
                    
                    $alertContainer.html(alertHtml).fadeIn();
                },
                complete: function() {
                    // Убираем индикатор загрузки
                    $submitBtn.prop('disabled', false).removeClass('loading');
                }
            });
            
            return false;
        });
    }
    
    // Инициализация при загрузке страницы
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initContactForm);
    } else {
        initContactForm();
    }
    
    // Также инициализируем при загрузке jQuery
    if (typeof jQuery !== 'undefined') {
        jQuery(document).ready(initContactForm);
    }
})(); 