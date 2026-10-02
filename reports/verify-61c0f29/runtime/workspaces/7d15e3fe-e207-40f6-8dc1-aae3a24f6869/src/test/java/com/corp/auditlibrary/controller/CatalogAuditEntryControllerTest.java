package com.corp.auditlibrary.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.CatalogAuditEntryResponse;
import com.corp.auditlibrary.model.dto.CreateCatalogAuditEntryRequest;
import com.corp.auditlibrary.service.CatalogAuditEntryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(controllers = CatalogAuditEntryController.class)
class CatalogAuditEntryControllerTest {

    private static final String ISBN = "9783161484100";
    private static final Instant OCCURRED_AT = Instant.parse("2024-05-01T10:15:30Z");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private CatalogAuditEntryService catalogAuditEntryService;

    @Test
    void createCatalogAuditEntry_withValidBody_respondsCreatedWithLocationHeaderAndRepresentation() throws Exception {
        UUID id = UUID.randomUUID();
        given(catalogAuditEntryService.createCatalogAuditEntry(any(CreateCatalogAuditEntryRequest.class)))
                .willReturn(new CatalogAuditEntryResponse(
                        id, ISBN, "CREATE", "librarian", "SUCCESS", "Book registered", OCCURRED_AT));

        String body = mockMvc.perform(post("/api/v1/catalog-audit-entries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"9783161484100","operation":"CREATE","actor":"librarian","outcome":"SUCCESS","detail":"Book registered"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().string(HttpHeaders.LOCATION, "/api/v1/catalog-audit-entries/" + id))
                .andReturn()
                .getResponse()
                .getContentAsString();

        CatalogAuditEntryResponse created = objectMapper.readValue(body, CatalogAuditEntryResponse.class);
        assertThat(created.id()).isEqualTo(id);
        assertThat(created.isbn()).isEqualTo(ISBN);
        assertThat(created.operation()).isEqualTo("CREATE");
        assertThat(created.actor()).isEqualTo("librarian");
        assertThat(created.outcome()).isEqualTo("SUCCESS");
        assertThat(created.detail()).isEqualTo("Book registered");
        assertThat(created.occurredAt()).isEqualTo(OCCURRED_AT);
    }

    @Test
    void createCatalogAuditEntry_withUnsupportedOperation_respondsBadRequestWithFieldErrorAndNeverReachesTheService() throws Exception {
        String body = mockMvc.perform(post("/api/v1/catalog-audit-entries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"9783161484100","operation":"ARCHIVE","actor":"librarian","outcome":"SUCCESS"}
                                """))
                .andExpect(status().isBadRequest())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat((String) JsonPath.read(body, "$.fieldErrors.operation")).isNotBlank();
        verifyNoInteractions(catalogAuditEntryService);
    }

    @Test
    void getCatalogAuditEntry_withKnownId_respondsOkWithFullRepresentation() throws Exception {
        UUID id = UUID.randomUUID();
        given(catalogAuditEntryService.getCatalogAuditEntry(id))
                .willReturn(new CatalogAuditEntryResponse(
                        id, ISBN, "READ", "auditor", "SUCCESS", null, OCCURRED_AT));

        String body = mockMvc.perform(get("/api/v1/catalog-audit-entries/{id}", id))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        CatalogAuditEntryResponse entry = objectMapper.readValue(body, CatalogAuditEntryResponse.class);
        assertThat(entry.id()).isEqualTo(id);
        assertThat(entry.isbn()).isEqualTo(ISBN);
        assertThat(entry.operation()).isEqualTo("READ");
        assertThat(entry.actor()).isEqualTo("auditor");
        assertThat(entry.outcome()).isEqualTo("SUCCESS");
        assertThat(entry.occurredAt()).isEqualTo(OCCURRED_AT);
    }

    @Test
    void getCatalogAuditEntry_withUnknownId_respondsNotFound() throws Exception {
        UUID id = UUID.randomUUID();
        given(catalogAuditEntryService.getCatalogAuditEntry(id))
                .willThrow(new ResourceNotFoundException("CatalogAuditEntry not found with id: " + id));

        String body = mockMvc.perform(get("/api/v1/catalog-audit-entries/{id}", id))
                .andExpect(status().isNotFound())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(404);
        assertThat((String) JsonPath.read(body, "$.message"))
                .isEqualTo("CatalogAuditEntry not found with id: " + id);
    }

    @Test
    void getAllCatalogAuditEntries_respondsOkWithEveryStoredEntry() throws Exception {
        UUID firstId = UUID.randomUUID();
        UUID secondId = UUID.randomUUID();
        given(catalogAuditEntryService.getAllCatalogAuditEntries())
                .willReturn(List.of(
                        new CatalogAuditEntryResponse(firstId, ISBN, "CREATE", "librarian", "SUCCESS", null, OCCURRED_AT),
                        new CatalogAuditEntryResponse(secondId, ISBN, "DELETE", "librarian", "FAILURE", "missing", OCCURRED_AT)));

        String body = mockMvc.perform(get("/api/v1/catalog-audit-entries"))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        CatalogAuditEntryResponse[] entries = objectMapper.readValue(body, CatalogAuditEntryResponse[].class);
        assertThat(entries).hasSize(2);
        assertThat(entries).extracting(CatalogAuditEntryResponse::id)
                .containsExactlyInAnyOrder(firstId, secondId);
    }

    @Test
    void deleteCatalogAuditEntry_withKnownId_respondsNoContent() throws Exception {
        UUID id = UUID.randomUUID();

        mockMvc.perform(delete("/api/v1/catalog-audit-entries/{id}", id))
                .andExpect(status().isNoContent());

        verify(catalogAuditEntryService).deleteCatalogAuditEntry(id);
    }

    @Test
    void deleteCatalogAuditEntry_withUnknownId_respondsNotFound() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new ResourceNotFoundException("CatalogAuditEntry not found with id: " + id))
                .given(catalogAuditEntryService)
                .deleteCatalogAuditEntry(id);

        String body = mockMvc.perform(delete("/api/v1/catalog-audit-entries/{id}", id))
                .andExpect(status().isNotFound())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(404);
        assertThat((String) JsonPath.read(body, "$.message"))
                .isEqualTo("CatalogAuditEntry not found with id: " + id);
    }
}
