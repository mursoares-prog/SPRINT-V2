package com.abandono;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
public class SpaController {

    // Encaminha qualquer rota sem extensão de arquivo para o index.html do React
    @RequestMapping(value = { "/", "/{path:[^\\.]*}", "/{path:[^\\.]*}/**" })
    public String forward() {
        return "forward:/index.html";
    }
}
