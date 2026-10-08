from app.services.devops_service import generate_all_devops_assets


def test_assets_run_real_native_checks_and_never_skip_tests(tmp_path):
    (tmp_path/'pom.xml').write_text('<project><modelVersion>4.0.0</modelVersion><dependencies/></project>')
    bundle=generate_all_devops_assets(str(tmp_path),'native-ci','ledger-service','H2',18088)
    assert 'DskipTests' not in bundle.dockerfileContent
    assert 'mvn' in bundle.dockerfileContent and 'verify' in bundle.dockerfileContent
    assert 'quarkus-app' in bundle.dockerfileContent and 'BOOT-INF' not in bundle.dockerfileContent
    assert 'echo' not in bundle.githubActionsWorkflow
    assert 'local-ci.py' in bundle.githubActionsWorkflow
    assert (tmp_path/'prepare-builder.py').is_file()
    assert (tmp_path/'local-ci.py').is_file()
    assert '--allow-network' in (tmp_path/'prepare-builder.py').read_text()
