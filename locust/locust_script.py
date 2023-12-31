import random
import math
from locust import HttpUser, TaskSet, task, constant
from locust import LoadTestShape


class UserTasks(TaskSet):
    @task
    def accelerated_ramp_up(self):
        count = random.randint(1, 10)
        url = f"/api/store-events-producer-fn?count={count}"
        self.client.get(f"{url}")


class WebsiteUser(HttpUser):
    wait_time = constant(0.5)
    tasks = [UserTasks]


class StepLoadShape(LoadTestShape):
    """
    A step load shape


    Keyword arguments:

        step_time -- Time between steps
        step_load -- User increase amount at each step
        spawn_rate -- Users to stop/start per second at every step
        time_limit -- Time limit in seconds

    """

    step_time = 1
    step_load = 50
    spawn_rate = 100
    time_limit = 300

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = math.floor(run_time / self.step_time) + 1
        return (current_step * self.step_load, self.spawn_rate)


# Run Locust with the customized parameters
# Use the following command in the terminal to run Locust:
# locust -f locust_script.py --host=https://your-api-url --users=500 --spawn-rate=<calculated_hatch_rate> --run-time=15 --headless
# locust -f locust_script.py --host=https://latency-store-front-us-apim-004.azure-api.net/ -u=50 -r=10 --run-time=1


# TARGET_HOST=https://latency-store-front-us-apim-006.azure-api.net
# locust -f locust_script.py --host=${TARGET_HOST} -u 10000 -r 1 -t 2m --logfile miztiik-locust.log --csv-full-history --csv=latency_store_front_us_apim
