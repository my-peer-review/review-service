pipeline {
  agent { label 'unit-test' }

  environment {
    CI_IMAGE_NAME   = 'assignments-pytest'
    APP_IMAGE_NAME  = 'ale175/service-assignment'
    DOCKERHUB_CREDS = 'dockerhub-creds'
    INTEGRATION_JOB = 'peer-review-pipeline/integration-repo/main' // <— ADATTA a come si chiama da te
  }

  stages {
    stage('Build CI Image & Unit Tests') {
      steps {
        sh 'docker build -t "${CI_IMAGE_NAME}" -f ./test/Dockerfile.unit .'
        sh '''
          docker run --rm \
            --user "$(id -u)":"$(id -g)" \
            -e ENV="unit-test" \
            -v "${PWD}:/work" -w /work \
            "${CI_IMAGE_NAME}" sh -c 'pytest -v test/pytest && rm -rf .pytest_cache'
        '''
      }
    }

    stage('Build & Push :latest (PR→main)') {
      when {
        allOf {
          changeRequest()
          expression { return env.CHANGE_TARGET == 'main' }
        }
      }
      steps {
        script {
          docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDS) {
            def appImage = docker.build("${APP_IMAGE_NAME}", "-f Dockerfile .")
            appImage.push("latest")
          }
        }
      }
    }

    stage('Trigger integrazione e attendi') {
      when {
        allOf {
          changeRequest()
          expression { return env.CHANGE_TARGET == 'main' }
        }
      }
      steps {
        script {
          // Attendi il job di integrazione e propaga lo stato:
          build job: INTEGRATION_JOB,
                wait: true,                // <— aspetta che finisca
                propagate: true,           // <— se fallisce, fallisce anche questa pipeline
                parameters: [
                  string(name: 'SERVICE_NAME', value: 'assignment'),
                  string(name: 'TRIGGER_TYPE', value: 'single')
                ]
        }
      }
    }
  }

  post {
    success { echo '✅ OK: unit, push (se PR→main) e integrazione passati.' }
    failure { echo '❌ KO: controlla i log (unit/push/integrazione).' }
    always  {
      sh '''
        rm -rf .pytest_cache || true
        sh sudo chown -R $(id -u):$(id -g) . || true
      '''
      deleteDir()
    }
  }
}
