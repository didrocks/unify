var timerlen = 5;
var animationlenght = 500;
var timer_id = new Array();
var start_time = new Array();

var divs = new Array();
var div_height = new Array();
var div_animation_dir = new Array();

addEvent(window, "load", collapsable_init);

function collapsable_init() {
	// Find all div with class collapsable and make them collapsable
	if (!document.getElementsByTagName) return;
	var divs = document.getElementsByTagName("div");
	for (i=0; i<divs.length; i++) {
		thisdiv = divs[i];
		if ((thisdiv.className == "collapsable" || thisdiv.className == "hiddencollapsable") && (thisdiv.id)) {
		    if (thisdiv.className == "hiddencollapsable")
		        thisdiv.style.display = "none";
		    // look for previous h2 tag
		    var node = thisdiv;
		    do {
		        node = node.previousSibling;
	        } while ((node.nodeName.toLowerCase() != "h2") && (node.nodeName.toLowerCase() != "h3"))
		    
		    node.innerHTML = '<a href="javascript:;" onclick="tooglesliding(\'' + thisdiv.id + '\');">' + node.innerHTML + '</a>';
		}
	}
}

function tooglesliding(objname){
    // if already sliding, invert the sense and compute new virtual start time
    if(divs[objname]) {
        start_time[objname] = 2 * (new Date()).getTime() - start_time[objname] - animationlenght;
        if(div_animation_dir[objname] == "show")
            div_animation_dir[objname] = "hide";
        else
            div_animation_dir[objname] = "show";
    }
    else {
        divs[objname] = document.getElementById(objname);
        if(divs[objname].style.display == "none") {
            div_animation_dir[objname] = "show";
            divs[objname].style.display = "block";
            div_height[objname] = parseInt(divs[objname].offsetHeight);
            divs[objname].style.height = "1px";
        }
        else {
            div_animation_dir[objname] = "hide";
            div_height[objname] = parseInt(divs[objname].offsetHeight); // need to repeat it, as we need to ensure we are displaying: block before in the previous case and before we force the height
        }
        start_time[objname] = (new Date()).getTime();
        timer_id[objname] = setInterval(slidetick, timerlen, objname);
    }
}


function slidetick(objname){
    var elapsed = (new Date()).getTime() - start_time[objname];
 
    if (elapsed > animationlenght)
        endsliding(objname);
    else {
        var inc = Math.round(elapsed / animationlenght * div_height[objname]);
        if(div_animation_dir[objname] == "hide")
            inc = div_height[objname] - inc;
        divs[objname].style.height = inc + "px";
        divs[objname].style.opacity = inc/div_height[objname]
     }
 
  return;
}

function endsliding(objname){
    clearInterval(timer_id[objname]);
 
    if(div_animation_dir[objname] == "hide")
        divs[objname].style.display = "none";
 
    divs[objname].style.height = div_height[objname] + "px";
 
    delete(timer_id[objname]);
    delete(start_time[objname]);
    delete(div_height[objname]);
    delete(divs[objname]);
    delete(div_animation_dir[objname]);
 
    return;
}
