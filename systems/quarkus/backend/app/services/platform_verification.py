"""Platform-owned Quarkus persistence gate, independent of generated unit-test mocks."""
import re
from pathlib import Path

def inject_contract_test(workspace_path):
    ws=Path(workspace_path)
    sources=list((ws/'src/main/java').rglob('*.java'))
    packages=[]
    for file in sources:
        if file.is_symlink() or not file.resolve().is_relative_to(ws.resolve()): raise ValueError('Linked Java source rejected')
        source=file.read_text(encoding='utf-8')
        if '@Entity' in source:
            match=re.search(r'package\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;',source)
            if match: packages.append(match.group(1))
    if not packages or not (ws/'src/main/resources/db/migration/h2/V1__initial.sql').is_file(): return None
    package=sorted(packages)[0]+'.platformverification'
    relative='src/test/java/'+package.replace('.','/')+'/PlatformPersistenceContractTest.java'
    target=ws/relative;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('package '+package+';\n'+"""
import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.QuarkusTestProfile;
import io.quarkus.test.junit.TestProfile;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertFalse;

@QuarkusTest
@TestProfile(PlatformPersistenceContractTest.StrictProfile.class)
public class PlatformPersistenceContractTest {
    public static class StrictProfile implements QuarkusTestProfile {
        public Map<String,String> getConfigOverrides() {
            return Map.of("quarkus.hibernate-orm.database.generation", "validate", "quarkus.flyway.migrate-at-start", "true", "quarkus.flyway.clean-disabled", "true");
        }
    }
    @Inject EntityManager entityManager;
    @Test void nativeSchemaAndMappingsMustAgree() {
        assertFalse(entityManager.getMetamodel().getEntities().isEmpty(), "A native persistent domain is required");
    }
}
""",encoding='utf-8')
    return relative
