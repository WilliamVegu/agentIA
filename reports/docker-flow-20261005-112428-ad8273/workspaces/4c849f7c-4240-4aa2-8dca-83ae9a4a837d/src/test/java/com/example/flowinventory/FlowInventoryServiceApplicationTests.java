package com.example.flowinventory;

import com.example.flowinventory.repository.ItemRepository;
import com.example.flowinventory.service.ItemService;
import com.example.flowinventory.service.impl.ItemServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Context-load test for the Spring Boot entry point.
 *
 * It asserts that the generated configuration (application entry point, service
 * implementation and repository) is discovered and wired inside a real Spring
 * context backed by the in-memory datasource declared in application.yml.
 */
@SpringBootTest
class FlowInventoryServiceApplicationTests {

    @Autowired
    private ApplicationContext applicationContext;

    @Test
    void contextLoadsWithFlowInventoryServiceBeans() {
        assertThat(applicationContext.getBean(FlowInventoryServiceApplication.class)).isNotNull();
        assertThat(applicationContext.getBean(ItemService.class)).isInstanceOf(ItemServiceImpl.class);
        assertThat(applicationContext.getBean(ItemRepository.class)).isNotNull();
    }
}
