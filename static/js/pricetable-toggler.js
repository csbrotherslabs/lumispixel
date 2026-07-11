
(function ($) {
	'use strict';
	
	jQuery(document).ready(function () {

        // Pricetable Toggler
        var e = document.getElementById("filt-monthly"),
            d = document.getElementById("filt-yearly"),
            t = document.getElementById("switcher"),
            m = document.getElementById("monthly"),
            y = document.getElementById("yearly");

        e.addEventListener("click", function(){
            t.checked = false;
            e.classList.add("toggler--is-active");
            d.classList.remove("toggler--is-active");
            m.classList.remove("d-none");
            y.classList.add("d-none");
        });

        d.addEventListener("click", function(){
            t.checked = true;
            d.classList.add("toggler--is-active");
            e.classList.remove("toggler--is-active");
            m.classList.add("d-none");
            y.classList.remove("d-none");
        });

        t.addEventListener("click", function(){
            d.classList.toggle("toggler--is-active");
            e.classList.toggle("toggler--is-active");
            m.classList.toggle("d-none");
            y.classList.toggle("d-none");
        });


    });      
})(jQuery);